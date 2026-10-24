/**
 * DataManagementPage - Data export and backup management
 *
 * Provides functionality for:
 * - Scheduling and managing data exports
 * - Viewing export job history and status
 * - Creating database backups
 *
 * @module pages/DataManagementPage
 * @see NEM-3177
 */

import { useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  Archive,
  Calendar,
  CheckCircle,
  Clock,
  Download,
  FileJson,
  FileSpreadsheet,
  FolderArchive,
  Loader2,
  Play,
  RefreshCw,
  Save,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import { BackupSection } from '../components/backup';
import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ExportColumnSelector from '../components/exports/ExportColumnSelector';
import { useExportJobsQuery, useStartExportJob, useCancelExportJob } from '../hooks/useExportJobs';
import { useSystemConfigQuery } from '../hooks/useSystemConfigQuery';
import { useToast } from '../hooks/useToast';
import { downloadExportFile, updateConfig } from '../services/api';
import { queryKeys } from '../services/queryClient';
import {
  formatFileSize,
  formatFilterParams,
  calculateDuration,
  formatDuration,
} from '../types/export';

import type {
  ExportJob,
  ExportType,
  ExportFormat,
  ExportJobCreateParams,
  ExportColumnName,
} from '../types/export';

// ============================================================================
// Types
// ============================================================================

interface ExportFormState {
  exportType: ExportType;
  exportFormat: ExportFormat;
  startDate: string;
  endDate: string;
  columns: ExportColumnName[] | null;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * StatusBadge displays the current status of an export job with appropriate styling.
 */
function StatusBadge({ status }: { status: ExportJob['status'] }) {
  const statusConfig = {
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${config.className}`}
    >
      <Icon className={`h-3.5 w-3.5 ${status === 'running' ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

/**
 * FormatIcon displays the appropriate icon for an export format.
 */
function FormatIcon({ format }: { format: string }) {
  switch (format) {
    case 'csv':
    case 'excel':
      return <FileSpreadsheet className="h-4 w-4 text-green-400" />;
    case 'json':
      return <FileJson className="h-4 w-4 text-blue-400" />;
    case 'zip':
      return <FolderArchive className="h-4 w-4 text-purple-400" />;
    default:
      return <Archive className="h-4 w-4 text-gray-400" />;
  }
}

/**
 * ProgressBar displays the progress of a running export job.
 */
function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-700">
      <div
        className="h-full rounded-full bg-primary transition-all duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

// ============================================================================
// Export Form Component
// ============================================================================

interface ExportFormProps {
  onStartExport: (params: ExportJobCreateParams) => Promise<void>;
  isLoading: boolean;
}

function ExportForm({ onStartExport, isLoading }: ExportFormProps) {
  const [formState, setFormState] = useState<ExportFormState>({
    exportType: 'events',
    exportFormat: 'csv',
    startDate: '',
    endDate: '',
    columns: null, // null = all columns
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onStartExport({
      export_type: formState.exportType,
      export_format: formState.exportFormat,
      start_date: formState.startDate || null,
      end_date: formState.endDate || null,
      columns: formState.columns,
    });
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Export Type */}
        <div>
          <label htmlFor="exportType" className="mb-2 block text-sm font-medium text-gray-300">
            Export Type
          </label>
          <select
            id="exportType"
            value={formState.exportType}
            onChange={(e) =>
              setFormState((prev) => ({ ...prev, exportType: e.target.value as ExportType }))
            }
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="events">Events</option>
            <option value="alerts">Alerts</option>
            <option value="full_backup">Full Backup</option>
          </select>
        </div>

        {/* Export Format */}
        <div>
          <label htmlFor="exportFormat" className="mb-2 block text-sm font-medium text-gray-300">
            Format
          </label>
          <select
            id="exportFormat"
            value={formState.exportFormat}
            onChange={(e) =>
              setFormState((prev) => ({ ...prev, exportFormat: e.target.value as ExportFormat }))
            }
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
            <option value="excel">Excel</option>
            <option value="zip">ZIP Archive</option>
          </select>
        </div>

        {/* Start Date */}
        <div>
          <label htmlFor="startDate" className="mb-2 block text-sm font-medium text-gray-300">
            Start Date
          </label>
          <div className="relative">
            <input
              type="date"
              id="startDate"
              value={formState.startDate}
              onChange={(e) => setFormState((prev) => ({ ...prev, startDate: e.target.value }))}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Calendar className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          </div>
        </div>

        {/* End Date */}
        <div>
          <label htmlFor="endDate" className="mb-2 block text-sm font-medium text-gray-300">
            End Date
          </label>
          <div className="relative">
            <input
              type="date"
              id="endDate"
              value={formState.endDate}
              onChange={(e) => setFormState((prev) => ({ ...prev, endDate: e.target.value }))}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Calendar className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          </div>
        </div>
      </div>

      {/* Column Selection */}
      {formState.exportType === 'events' && (
        <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
          <ExportColumnSelector
            selectedColumns={formState.columns}
            onChange={(columns) => setFormState((prev) => ({ ...prev, columns }))}
            disabled={isLoading}
          />
        </div>
      )}

      <Button
        type="submit"
        variant="primary"
        leftIcon={<Play className="h-4 w-4" />}
        isLoading={isLoading}
        disabled={isLoading}
      >
        Start Export
      </Button>
    </form>
  );
}

// ============================================================================
// Export Job Card Component
// ============================================================================

interface ExportJobCardProps {
  job: ExportJob;
  onCancel: (jobId: string) => Promise<void>;
  onDownload: (jobId: string) => Promise<void>;
  isCancelling: boolean;
}

function ExportJobCard({ job, onCancel, onDownload, isCancelling }: ExportJobCardProps) {
  const canCancel = job.status === 'pending' || job.status === 'running';
  const canDownload = job.status === 'completed' && job.result?.output_path;
  const filters = formatFilterParams(job.filter_params);
  const duration = calculateDuration(job.started_at, job.completed_at);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid={`export-job-${job.id}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <FormatIcon format={job.export_format} />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-white">{job.id.slice(0, 8)}...</span>
              <StatusBadge status={job.status} />
            </div>
            <div className="mt-1 text-sm text-gray-400">
              {job.export_type} - {job.export_format.toUpperCase()}
            </div>
            <div className="mt-1 text-xs text-gray-500">Created: {formatDate(job.created_at)}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {canCancel && (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<X className="h-4 w-4" />}
              onClick={() => void onCancel(job.id)}
              disabled={isCancelling}
            >
              Cancel
            </Button>
          )}
          {canDownload && (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Download className="h-4 w-4" />}
              onClick={() => void onDownload(job.id)}
            >
              Download
            </Button>
          )}
        </div>
      </div>

      {/* Progress for running jobs */}
      {job.status === 'running' && (
        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-gray-400">{job.progress.current_step}</span>
            <span className="font-medium text-white">{job.progress.progress_percent}%</span>
          </div>
          <ProgressBar percent={job.progress.progress_percent} />
          {job.progress.total_items && (
            <div className="mt-1 text-xs text-gray-500">
              {job.progress.processed_items.toLocaleString()} /{' '}
              {job.progress.total_items.toLocaleString()} items
            </div>
          )}
        </div>
      )}

      {/* Result for completed jobs */}
      {job.status === 'completed' && job.result && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-400">
            <span>{job.result.event_count.toLocaleString()} records</span>
            <span>{formatFileSize(job.result.output_size_bytes)}</span>
            {duration !== null && <span>Duration: {formatDuration(duration)}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            {job.started_at && <span>Started: {formatDate(job.started_at)}</span>}
            {job.completed_at && <span>Completed: {formatDate(job.completed_at)}</span>}
          </div>
        </div>
      )}

      {/* Filter metadata */}
      {filters.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {filters.map((filter) => (
            <span
              key={filter}
              className="inline-flex items-center rounded-full border border-gray-600 bg-gray-700/50 px-2 py-0.5 text-xs text-gray-300"
            >
              {filter}
            </span>
          ))}
        </div>
      )}

      {/* Error for failed jobs */}
      {job.status === 'failed' && job.error_message && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-500/10 p-3">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
          <span className="text-sm text-red-300">{job.error_message}</span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Trash Retention Section (F4.3)
// ============================================================================

/**
 * TrashRetentionSection edits `trash_retention_days` — the Trash clock that
 * purges soft-deleted events at `deleted_at + N days` (the earlier of that
 * and general retention, mirrored in src/utils/trashPurge.ts). The spec
 * (4n-trash.md) places the setting under Settings › Data. 0 disables the
 * Trash clock; general retention still purges.
 */
function TrashRetentionSection() {
  const { data: config, isLoading: configLoading } = useSystemConfigQuery();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editedDays, setEditedDays] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // null editedDays = not yet seeded from config; seeding happens in the
  // derive step below rather than a useEffect so the first render already
  // carries the server value (LoggingSettings seeds state in an effect,
  // which flashes the fallback 7 for a frame).
  const originalDays = config?.trash_retention_days;
  const days = editedDays ?? originalDays;
  const hasChanges = days !== null && originalDays !== undefined && days !== originalDays;

  const handleSave = useCallback(async () => {
    if (days === null || !hasChanges) return;

    setIsSaving(true);
    try {
      // Partial PATCH: only the changed key travels (ConfigUpdateRequest
      // fields are all optional; the backend applies non-null fields).
      await updateConfig({ trash_retention_days: days });
      // Drop the cached config so this card (and the TrashPage chips, which
      // share the query) refetch the server's value rather than showing the
      // stale pre-save number for the next 5 staleTime minutes.
      await queryClient.invalidateQueries({ queryKey: queryKeys.system.config });
      setEditedDays(null); // back to "clean" — days now derives from config
      toast.success(`Trash retention updated to ${days} days`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update trash retention');
    } finally {
      setIsSaving(false);
    }
  }, [days, hasChanges, toast, queryClient]);

  const handleReset = useCallback(() => {
    setEditedDays(null);
  }, []);

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-6"
      data-testid="trash-retention-settings"
    >
      <div className="mb-4 flex items-center gap-2">
        <Trash2 className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold text-white">Trash Retention</h2>
      </div>

      {configLoading || originalDays === undefined ? (
        <p className="text-sm text-gray-400">
          {configLoading
            ? 'Loading current setting…'
            : 'This deployment does not report a Trash retention setting.'}
        </p>
      ) : (
        <>
          <div className="mb-2 flex items-end justify-between">
            <div>
              <p className="text-sm text-gray-300">Days to keep deleted events in Trash</p>
              <p className="mt-1 text-xs text-gray-500">
                Deleted events are purged at the earlier of this clock and general retention. 0
                disables the Trash clock — general retention alone then purges them.
              </p>
            </div>
            <p className="text-lg font-semibold text-white" data-testid="trash-retention-value">
              {days} {days === 1 ? 'day' : 'days'}
            </p>
          </div>
          <input
            type="range"
            min="0"
            max="365"
            step="1"
            value={days}
            onChange={(e) => setEditedDays(parseInt(e.target.value, 10))}
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
            aria-label="Trash retention in days"
            data-testid="trash-retention-slider"
          />
          <div className="mt-1 flex justify-between text-xs text-gray-500">
            <span>Off (0)</span>
            <span>365 days</span>
          </div>

          {/* Action buttons */}
          <div className="mt-4 flex gap-3 border-t border-gray-700 pt-4">
            <Button
              onClick={() => void handleSave()}
              disabled={!hasChanges}
              isLoading={isSaving}
              leftIcon={<Save className="h-4 w-4" />}
              data-testid="trash-retention-save"
            >
              Save
            </Button>
            <Button
              variant="ghost"
              onClick={handleReset}
              disabled={!hasChanges || isSaving}
              data-testid="trash-retention-reset"
            >
              Reset
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * DataManagementPage provides data export and backup functionality.
 */
export default function DataManagementPage() {
  const { jobs, isPending, isLoading, isError, error, refetch } = useExportJobsQuery({
    refetchInterval: 5000, // Poll for updates every 5 seconds
  });
  const { startExport, isPending: isStarting } = useStartExportJob();
  const { cancelJob, isPending: isCancelling } = useCancelExportJob();

  const handleStartExport = useCallback(
    async (params: ExportJobCreateParams) => {
      await startExport(params);
    },
    [startExport]
  );

  const handleCancelJob = useCallback(
    async (jobId: string) => {
      await cancelJob(jobId);
    },
    [cancelJob]
  );

  const handleDownloadJob = useCallback(async (jobId: string) => {
    await downloadExportFile(jobId);
  }, []);

  // Loading state - check both isPending (no data yet) and isLoading (initial fetch)
  // In TanStack Query v5, isPending means status === 'pending' (no cached data)
  // This handles edge cases where isLoading might be false but data isn't available
  if (isPending || isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center" data-testid="loading-spinner">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-6" data-testid="data-management-page">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Failed to load export jobs</span>
          </div>
          <p className="mt-2 text-sm text-red-300">{error?.message}</p>
          <button
            onClick={() => void refetch()}
            className="mt-3 rounded bg-red-500/20 px-3 py-1 text-sm text-red-300 hover:bg-red-500/30"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="data-management-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-page-title">Data Management</h1>
          <p className="text-body-sm mt-2">
            Export data and create backups of your security system
          </p>
        </div>

        <div className="space-y-8">
          {/* Export Section */}
          <div className="grid gap-8 lg:grid-cols-2">
            {/* Export Form */}
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                  <Download className="h-5 w-5 text-primary" />
                  Export Data
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<RefreshCw className="h-4 w-4" />}
                  onClick={() => void refetch()}
                >
                  Refresh
                </Button>
              </div>

              <ExportForm onStartExport={handleStartExport} isLoading={isStarting} />
            </div>

            {/* Export Jobs List */}
            <div>
              <h2 className="mb-4 text-lg font-semibold text-white">Export History</h2>

              {jobs.length === 0 ? (
                <EmptyState
                  icon={Archive}
                  title="No export jobs"
                  description="Start an export to see your job history here."
                  variant="muted"
                  size="sm"
                />
              ) : (
                <div className="space-y-4">
                  {jobs.map((job) => (
                    <ExportJobCard
                      key={job.id}
                      job={job}
                      onCancel={handleCancelJob}
                      onDownload={handleDownloadJob}
                      isCancelling={isCancelling}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Backup Section */}
          <BackupSection />

          {/* Trash Retention (F4.3) — the setting under Settings › Data */}
          <TrashRetentionSection />
        </div>
      </div>
    </div>
  );
}
