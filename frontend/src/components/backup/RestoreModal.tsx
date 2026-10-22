/**
 * RestoreModal Component
 *
 * Modal dialog for restore operations with file upload, automatic safety backup
 * link, per-table merge summary, added rows and cleared known-person links by
 * name, and detailed failure reporting (B4.6 / 4n-restore.md).
 *
 * @module components/backup/RestoreModal
 * @see NEM-3566
 */

import { clsx } from 'clsx';
import { AlertTriangle, CheckCircle, RotateCcw, Upload, X, XCircle } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import BackupProgress from './BackupProgress';
import {
  isRestoreJobComplete,
  isRestoreJobFailed,
  isRestoreJobInProgress,
  useRestoreJob,
  useStartRestore,
} from '../../hooks/useBackup';
import { getBackupDownloadUrl } from '../../services/backupApi';
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

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) {
        setIsDragOver(true);
      }
    },
    [disabled]
  );

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
        <p className="font-medium text-yellow-400">Configuration will be merged</p>
        <p className="mt-1 text-sm text-yellow-300/80">
          An automatic &ldquo;before restore&rdquo; safety backup is saved first. Restoring merges
          configuration tables and replaces baselines for cameras in the backup while keeping your
          event history intact. Restoring the safety backup reverts changed rows and baselines; rows
          added by the restore remain and are listed below.
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
          {job.backup_created_at &&
            ` (created ${new Date(job.backup_created_at).toLocaleDateString()})`}
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
  onRestoreSafetyBackup: (safetyBackupId: string) => void | Promise<void>;
}

function formatTableLabel(table: string): string {
  return table.replace(/_/g, ' ');
}

function CompleteState({ job, onClose, onRestoreSafetyBackup }: CompleteStateProps) {
  const itemsRestored = job.items_restored ?? {};
  const tableStats = job.tables ?? {};
  const addedRows = job.added_rows ?? {};
  const clearedLinks = job.cleared_known_person_links ?? [];
  const skippedTables = job.skipped_tables ?? [];
  const safetyBackupId = job.safety_backup_id;
  const totalItems = Object.values(itemsRestored).reduce((sum, count) => sum + count, 0);

  const addedEntries = Object.entries(addedRows).filter(([, names]) => names.length > 0);

  return (
    <div className="space-y-4" data-testid="complete-state">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
          <CheckCircle className="h-8 w-8 text-green-400" />
        </div>
        <h3 className="text-lg font-semibold text-white">Restore Complete</h3>
        <p className="mt-1 text-sm text-gray-400">Successfully restored {totalItems} items</p>
      </div>

      {/* Automatic Safety Backup Banner + Restore Link */}
      {safetyBackupId && (
        <div
          className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-sm"
          data-testid="safety-backup-banner"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-blue-200">
              Safety backup saved before restore:{' '}
              <code className="font-mono text-xs text-white">{safetyBackupId.slice(0, 8)}</code>
            </span>
            <div className="flex items-center gap-3">
              <a
                href={getBackupDownloadUrl(safetyBackupId)}
                className="text-xs font-medium text-blue-300 underline hover:text-white"
                data-testid="safety-backup-download-link"
              >
                Download safety backup
              </a>
              <button
                type="button"
                onClick={() => void onRestoreSafetyBackup(safetyBackupId)}
                className="inline-flex items-center gap-1 rounded bg-blue-500/20 px-2 py-1 text-xs font-medium text-blue-200 hover:bg-blue-500/30 hover:text-white"
                data-testid="safety-backup-restore-link"
              >
                <RotateCcw className="h-3 w-3" />
                Restore safety backup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Per-table Summary */}
      {Object.keys(itemsRestored).length > 0 && (
        <div
          className="max-h-48 overflow-y-auto rounded-lg bg-gray-800/50 p-4"
          data-testid="restore-table-summaries"
        >
          <p className="mb-2 text-sm font-medium text-gray-300">Items Restored:</p>
          <ul className="space-y-1.5 text-sm text-gray-400">
            {Object.entries(itemsRestored).map(([table, count]) => {
              const stats = tableStats[table];
              const label = formatTableLabel(table);
              const detailText = stats
                ? `restored ${count} ${label}, added ${stats.inserted}, kept ${stats.kept} not in this backup`
                : `restored ${count} ${label}`;
              return (
                <li
                  key={table}
                  className="flex flex-col justify-between gap-0.5 sm:flex-row sm:items-center"
                  data-testid={`restore-table-summary-${table}`}
                >
                  <span className="capitalize">{label}</span>
                  <span className="text-xs text-gray-300 sm:text-sm">
                    {detailText} (<span className="text-white">{count}</span>)
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Added Rows by Name */}
      {addedEntries.length > 0 && (
        <div className="rounded-lg bg-gray-800/50 p-4" data-testid="restore-added-rows">
          <p className="mb-2 text-sm font-medium text-gray-300">
            Added Rows (stay if safety backup is restored):
          </p>
          <ul className="space-y-1 text-xs text-gray-400">
            {addedEntries.map(([table, names]) => (
              <li key={table} data-testid={`restore-added-${table}`}>
                <span className="font-medium capitalize text-gray-300">
                  {formatTableLabel(table)}:
                </span>{' '}
                {names.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Cleared Known-Person Links by Name */}
      {clearedLinks.length > 0 && (
        <div className="rounded-lg bg-yellow-500/10 p-4" data-testid="restore-cleared-links">
          <p className="mb-1 text-sm font-medium text-yellow-300">
            Cleared Known-Person Links (re-enrolment required):
          </p>
          <p className="text-xs text-yellow-200/80">{clearedLinks.join(', ')}</p>
        </div>
      )}

      {/* Skipped Legacy Tables */}
      {skippedTables.length > 0 && (
        <div
          className="rounded-lg bg-gray-800/40 p-3 text-xs text-gray-400"
          data-testid="restore-skipped-tables"
        >
          Skipped legacy history tables: {skippedTables.join(', ')}
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
        <p className="mt-1 text-sm text-red-300" data-testid="restore-error-detail">
          {message}
        </p>
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

export default function RestoreModal({ isOpen, onClose, onRestoreComplete }: RestoreModalProps) {
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

  // Handle restoring directly from the automatic safety backup
  const handleRestoreSafetyBackup = useCallback(
    async (safetyBackupId: string) => {
      setUploadError(null);
      setModalState('uploading');
      try {
        const response = await fetch(`/api/backup/${encodeURIComponent(safetyBackupId)}/download`);
        if (!response.ok) {
          throw new Error(`Failed to download safety backup (${response.status})`);
        }
        const blob = await response.blob();
        const file = new File([blob], `safety_${safetyBackupId.slice(0, 8)}.zip`, {
          type: 'application/zip',
        });
        await handleFileSelect(file);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to restore safety backup';
        setUploadError(message);
        setErrorMessage(message);
        setModalState('error');
      }
    },
    [handleFileSelect]
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
    if (
      modalState === 'uploading' ||
      (modalState === 'restoring' && restoreJob && isRestoreJobInProgress(restoreJob))
    ) {
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

  const showCloseButton =
    modalState !== 'uploading' &&
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

        {modalState === 'restoring' && restoreJob && <RestoringState job={restoreJob} />}

        {modalState === 'complete' && restoreJob && (
          <CompleteState
            job={restoreJob}
            onClose={handleClose}
            onRestoreSafetyBackup={handleRestoreSafetyBackup}
          />
        )}

        {modalState === 'error' && (
          <ErrorState message={errorMessage} onRetry={handleRetry} onClose={handleClose} />
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
