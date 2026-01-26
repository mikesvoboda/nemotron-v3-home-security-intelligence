/**
 * BackupSection Component
 *
 * Main backup management section with create backup button,
 * backup list, and restore modal integration.
 *
 * @module components/backup/BackupSection
 * @see NEM-3566
 */

import { clsx } from 'clsx';
import { Database, Download, RefreshCw, Upload } from 'lucide-react';
import { useCallback, useState } from 'react';

import BackupList from './BackupList';
import BackupProgress from './BackupProgress';
import RestoreModal from './RestoreModal';
import {
  isBackupJobComplete,
  isBackupJobFailed,
  useBackupJob,
  useBackupList,
  useCreateBackup,
  useDeleteBackup,
} from '../../hooks/useBackup';
import Button from '../common/Button';

// ============================================================================
// Types
// ============================================================================

export interface BackupSectionProps {
  /** Optional CSS class */
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * BackupSection provides a complete backup management interface.
 *
 * Features:
 * - Create new backups with progress tracking
 * - View list of existing backups
 * - Download completed backups
 * - Delete backups with confirmation
 * - Restore from backup file with modal
 *
 * @example
 * ```tsx
 * <BackupSection />
 * ```
 */
export default function BackupSection({ className }: BackupSectionProps) {
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [activeBackupJobId, setActiveBackupJobId] = useState<string | null>(null);
  const [deletingBackupId, setDeletingBackupId] = useState<string | null>(null);

  // Queries and mutations
  const { data: backupListData, isLoading, isRefetching, error, refetch } = useBackupList();
  const { createBackup, isLoading: isCreating } = useCreateBackup();
  const { deleteBackup, isLoading: isDeleting } = useDeleteBackup();
  const { data: activeBackupJob } = useBackupJob(activeBackupJobId ?? '', {
    enabled: !!activeBackupJobId,
  });

  // Check if active job is complete and clear it
  if (activeBackupJob && isBackupJobComplete(activeBackupJob)) {
    // Delay clearing to show completion state briefly
    setTimeout(() => {
      setActiveBackupJobId(null);
      void refetch();
    }, 2000);
  }

  // Handle create backup
  const handleCreateBackup = useCallback(async () => {
    try {
      const response = await createBackup();
      setActiveBackupJobId(response.job_id);
    } catch (err) {
      // Error is handled by the mutation
      console.error('Failed to create backup:', err);
    }
  }, [createBackup]);

  // Handle delete backup
  const handleDeleteBackup = useCallback(
    async (backupId: string) => {
      setDeletingBackupId(backupId);
      try {
        await deleteBackup(backupId);
      } catch (err) {
        console.error('Failed to delete backup:', err);
      } finally {
        setDeletingBackupId(null);
      }
    },
    [deleteBackup]
  );

  // Handle restore complete
  const handleRestoreComplete = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Determine if we should show the active backup progress
  const showActiveBackup = activeBackupJob && !isBackupJobComplete(activeBackupJob);

  return (
    <div className={clsx('space-y-6', className)} data-testid="backup-section">
      {/* Header Card */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          {/* Info */}
          <div className="flex items-start gap-4">
            <div className="rounded-lg bg-purple-500/20 p-3">
              <Database className="h-6 w-6 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Database Backup</h3>
              <p className="mt-1 text-sm text-gray-400">
                Create full backups of your security monitoring database including events,
                detections, cameras, and configuration.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline-primary"
              leftIcon={<Database className="h-4 w-4" />}
              onClick={() => void handleCreateBackup()}
              isLoading={isCreating}
              disabled={isCreating || showActiveBackup}
            >
              Create Backup
            </Button>
            <Button
              variant="outline"
              leftIcon={<Upload className="h-4 w-4" />}
              onClick={() => setIsRestoreModalOpen(true)}
              disabled={showActiveBackup}
            >
              Restore
            </Button>
          </div>
        </div>

        {/* Active Backup Progress */}
        {showActiveBackup && (
          <div className="mt-6">
            <BackupProgress
              progress={activeBackupJob.progress}
              status={activeBackupJob.status}
              isComplete={isBackupJobComplete(activeBackupJob)}
              isFailed={isBackupJobFailed(activeBackupJob)}
              errorMessage={activeBackupJob.error_message}
            />
          </div>
        )}
      </div>

      {/* Backup List */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h4 className="flex items-center gap-2 text-base font-semibold text-white">
            <Download className="h-4 w-4 text-gray-400" />
            Available Backups
            {backupListData && (
              <span className="text-sm font-normal text-gray-400">
                ({backupListData.total})
              </span>
            )}
          </h4>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<RefreshCw className={clsx('h-4 w-4', isRefetching && 'animate-spin')} />}
            onClick={() => void refetch()}
            disabled={isRefetching}
          >
            Refresh
          </Button>
        </div>

        <BackupList
          backups={backupListData?.backups ?? []}
          isLoading={isLoading}
          isError={!!error}
          errorMessage={error?.message}
          onDelete={handleDeleteBackup}
          isDeleting={isDeleting}
          deletingId={deletingBackupId ?? undefined}
          onRetry={() => void refetch()}
        />
      </div>

      {/* Restore Modal */}
      <RestoreModal
        isOpen={isRestoreModalOpen}
        onClose={() => setIsRestoreModalOpen(false)}
        onRestoreComplete={handleRestoreComplete}
      />
    </div>
  );
}
