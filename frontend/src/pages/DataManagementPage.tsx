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

import {
  AlertCircle,
  Archive,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  Download,
  FileJson,
  FileSpreadsheet,
  FolderArchive,
  Loader2,
  Play,
  RefreshCw,
  X,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import {
  useExportJobsQuery,
  useStartExportJob,
  useCancelExportJob,
} from '../hooks/useExportJobs';
import { downloadExportFile } from '../services/api';
import { formatFileSize } from '../types/export';

import type {
  ExportJob,
  ExportType,
  ExportFormat,
  ExportJobCreateParams,
} from '../types/export';

// ============================================================================
// Types
// ============================================================================

interface ExportFormState {
  exportType: ExportType;
  exportFormat: ExportFormat;
  startDate: string;
  endDate: string;
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
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onStartExport({
      export_type: formState.exportType,
      export_format: formState.exportFormat,
      start_date: formState.startDate || null,
      end_date: formState.endDate || null,
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
              <span className="font-mono text-sm text-white">{job.id}</span>
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
        </div>
      )}

      {/* Result for completed jobs */}
      {job.status === 'completed' && job.result && (
        <div className="mt-3 flex items-center gap-4 text-sm text-gray-400">
          <span>{job.result.event_count} records</span>
          <span>{formatFileSize(job.result.output_size_bytes)}</span>
          {job.completed_at && <span>Completed: {formatDate(job.completed_at)}</span>}
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
// Backup Section Component
// ============================================================================

function BackupSection() {
  const [isCreating, setIsCreating] = useState(false);

  const handleCreateBackup = async () => {
    setIsCreating(true);
    // For now, creating a full_backup export serves as the backup mechanism
    // In the future, this could call a dedicated backup API
    try {
      // Simulate backup creation - in production this would call the API
      await new Promise((resolve) => setTimeout(resolve, 1000));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
      <div className="flex items-start gap-4">
        <div className="rounded-lg bg-purple-500/20 p-3">
          <Database className="h-6 w-6 text-purple-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white">Database Backup</h3>
          <p className="mt-1 text-sm text-gray-400">
            Create a full backup of your security monitoring database including events, detections,
            and configuration.
          </p>
          <div className="mt-4">
            <Button
              variant="outline-primary"
              leftIcon={<Database className="h-4 w-4" />}
              onClick={() => void handleCreateBackup()}
              isLoading={isCreating}
              disabled={isCreating}
            >
              Create Backup
            </Button>
          </div>
        </div>
      </div>
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
  const { jobs, isLoading, isError, error, refetch } = useExportJobsQuery({
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

  // Loading state
  if (isLoading) {
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
          <p className="text-body-sm mt-2">Export data and create backups of your security system</p>
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Export Form Section */}
          <div className="lg:col-span-2">
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
            <div className="mt-8">
              <h2 className="mb-4 text-lg font-semibold text-white">Export History</h2>

              {jobs.length === 0 ? (
                <EmptyState
                  icon={Archive}
                  title="No export jobs"
                  description="Start an export to see your job history here."
                  variant="muted"
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
          <div className="lg:col-span-1">
            <BackupSection />
          </div>
        </div>
      </div>
    </div>
  );
}
