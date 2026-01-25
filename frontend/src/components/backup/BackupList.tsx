/**
 * BackupList Component
 *
 * Displays a table/list of available backups with status indicators,
 * download links, and delete buttons.
 *
 * @module components/backup/BackupList
 * @see NEM-3566
 */

import { clsx } from 'clsx';
import {
  AlertCircle,
  Archive,
  CheckCircle,
  Clock,
  Download,
  Loader2,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import { getBackupDownloadUrl } from '../../hooks/useBackup';
import Button from '../common/Button';
import EmptyState from '../common/EmptyState';

import type { BackupListItem, BackupJobStatus } from '../../types/backup';

// ============================================================================
// Types
// ============================================================================

export interface BackupListProps {
  /** List of backup items */
  backups: BackupListItem[];
  /** Whether the list is loading */
  isLoading?: boolean;
  /** Whether there's an error */
  isError?: boolean;
  /** Error message if any */
  errorMessage?: string;
  /** Callback when delete is clicked */
  onDelete: (backupId: string) => Promise<void>;
  /** Whether a delete is in progress */
  isDeleting?: boolean;
  /** ID of backup currently being deleted */
  deletingId?: string;
  /** Callback when retry is clicked */
  onRetry?: () => void;
  /** Optional CSS class */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format file size to human-readable string.
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format date to locale string.
 */
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: BackupJobStatus;
}

function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig: Record<
    BackupJobStatus,
    {
      label: string;
      icon: typeof CheckCircle;
      className: string;
    }
  > = {
    pending: {
      label: 'Pending',
      icon: Clock,
      className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    },
    running: {
      label: 'Running',
      icon: Loader2,
      className: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    },
    completed: {
      label: 'Completed',
      icon: CheckCircle,
      className: 'bg-green-500/20 text-green-400 border-green-500/30',
    },
    failed: {
      label: 'Failed',
      icon: XCircle,
      className: 'bg-red-500/20 text-red-400 border-red-500/30',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
        config.className
      )}
    >
      <Icon className={clsx('h-3.5 w-3.5', status === 'running' && 'animate-spin')} />
      {config.label}
    </span>
  );
}

// ============================================================================
// Backup Row Component
// ============================================================================

interface BackupRowProps {
  backup: BackupListItem;
  onDelete: (backupId: string) => Promise<void>;
  isDeleting: boolean;
}

function BackupRow({ backup, onDelete, isDeleting }: BackupRowProps) {
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const canDownload = backup.status === 'completed' && backup.download_url;
  const canDelete = backup.status === 'completed' || backup.status === 'failed';

  const handleDeleteClick = () => {
    if (isConfirmingDelete) {
      setIsConfirmingDelete(false);
      void onDelete(backup.id);
    } else {
      setIsConfirmingDelete(true);
    }
  };

  const handleCancelDelete = () => {
    setIsConfirmingDelete(false);
  };

  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-gray-700 bg-gray-800/50 p-4 sm:flex-row sm:items-center sm:justify-between"
      data-testid={`backup-item-${backup.id}`}
    >
      {/* Backup Info */}
      <div className="flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-white">{backup.id.slice(0, 8)}...</span>
          <StatusBadge status={backup.status} />
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
          <span>Created: {formatDate(backup.created_at)}</span>
          {backup.file_size_bytes > 0 && <span>Size: {formatFileSize(backup.file_size_bytes)}</span>}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {isConfirmingDelete ? (
          <>
            <span className="mr-2 text-xs text-gray-400">Delete backup?</span>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDeleteClick}
              disabled={isDeleting}
              isLoading={isDeleting}
            >
              Confirm
            </Button>
            <Button variant="ghost" size="sm" onClick={handleCancelDelete} disabled={isDeleting}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            {canDownload && (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Download className="h-4 w-4" />}
                onClick={() => {
                  window.location.href = getBackupDownloadUrl(backup.id);
                }}
              >
                Download
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={handleDeleteClick}
                disabled={isDeleting}
              >
                Delete
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Loading State Component
// ============================================================================

function LoadingState() {
  return (
    <div className="space-y-4" data-testid="backup-list-loading">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex animate-pulse flex-col gap-3 rounded-lg border border-gray-700 bg-gray-800/50 p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-4 w-24 rounded bg-gray-700" />
              <div className="h-5 w-20 rounded-full bg-gray-700" />
            </div>
            <div className="h-3 w-48 rounded bg-gray-700" />
          </div>
          <div className="flex items-center gap-2">
            <div className="h-8 w-24 rounded bg-gray-700" />
            <div className="h-8 w-20 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Error State Component
// ============================================================================

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
      data-testid="backup-list-error"
    >
      <div className="flex items-center gap-2 text-red-400">
        <AlertCircle className="h-5 w-5" />
        <span className="font-medium">Failed to load backups</span>
      </div>
      {message && <p className="mt-2 text-sm text-red-300">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded bg-red-500/20 px-3 py-1 text-sm text-red-300 hover:bg-red-500/30"
        >
          Try Again
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * BackupList displays a list of available backups with actions.
 *
 * Features:
 * - Shows backup ID, status, creation date, and size
 * - Download button for completed backups
 * - Delete button with confirmation
 * - Loading and empty states
 * - Error state with retry
 *
 * @example
 * ```tsx
 * <BackupList
 *   backups={data?.backups ?? []}
 *   isLoading={isLoading}
 *   onDelete={deleteBackup}
 *   isDeleting={isDeleting}
 * />
 * ```
 */
export default function BackupList({
  backups,
  isLoading = false,
  isError = false,
  errorMessage,
  onDelete,
  isDeleting = false,
  deletingId,
  onRetry,
  className,
}: BackupListProps) {
  // Loading state
  if (isLoading) {
    return <LoadingState />;
  }

  // Error state
  if (isError) {
    return <ErrorState message={errorMessage} onRetry={onRetry} />;
  }

  // Empty state
  if (backups.length === 0) {
    return (
      <EmptyState
        icon={Archive}
        title="No backups"
        description="Create your first backup to protect your data."
        variant="muted"
        size="sm"
        testId="backup-list-empty"
      />
    );
  }

  // Backup list
  return (
    <div className={clsx('space-y-4', className)} data-testid="backup-list">
      {backups.map((backup) => (
        <BackupRow
          key={backup.id}
          backup={backup}
          onDelete={onDelete}
          isDeleting={isDeleting && deletingId === backup.id}
        />
      ))}
    </div>
  );
}
