import { Card, Title, Text, Badge, ProgressBar, Button } from '@tremor/react';
import { clsx } from 'clsx';
import {
  HardDrive,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Trash2,
  Download,
  FolderOpen,
  Image,
  Film,
  FileImage,
  CheckCircle,
  Clock,
  XCircle,
  PlayCircle,
  FileQuestion,
  Calendar,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchStorageStats,
  fetchJobs,
  fetchCleanupStatus,
  previewCleanup,
  triggerCleanup,
  previewOrphanedFiles,
  triggerOrphanedCleanup,
  type StorageStatsResponse,
  type JobListResponse,
  type JobResponse,
  type CleanupResponse,
  type CleanupStatusResponse,
  type OrphanedFileCleanupResponse,
} from '../../services/api';
import { useStorageStatusStore } from '../../stores/storage-status-store';

/**
 * Props for FileOperationsPanel component
 */
export interface FileOperationsPanelProps {
  /** Polling interval in milliseconds (default: 30000) */
  pollingInterval?: number;
  /** Optional callback when storage stats change */
  onStorageChange?: (stats: StorageStatsResponse) => void;
  /** Whether the panel starts expanded (default: true) */
  defaultExpanded?: boolean;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
  /** Optional className for styling */
  className?: string;
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

/**
 * Format number with commas
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Get status icon for job
 */
function getJobStatusIcon(status: string) {
  switch (status) {
    case 'running':
      return <PlayCircle className="h-4 w-4 text-[#76B900]" />;
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'pending':
    default:
      return <Clock className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * Get status badge color for job
 */
function getJobStatusColor(status: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (status) {
    case 'running':
      return 'green';
    case 'completed':
      return 'green';
    case 'failed':
      return 'red';
    case 'pending':
    default:
      return 'gray';
  }
}

/**
 * Storage category card component
 */
interface StorageCategoryProps {
  icon: React.ReactNode;
  label: string;
  fileCount: number;
  sizeBytes: number;
  testId: string;
}

function StorageCategory({ icon, label, fileCount, sizeBytes, testId }: StorageCategoryProps) {
  return (
    <div
      className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3"
      data-testid={testId}
    >
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <Text className="text-sm font-medium text-gray-300">{label}</Text>
          <Text className="text-xs text-gray-500">{formatNumber(fileCount)} files</Text>
        </div>
      </div>
      <Text className="text-sm font-medium text-white">{formatBytes(sizeBytes)}</Text>
    </div>
  );
}

/**
 * Export job row component
 */
interface ExportJobRowProps {
  job: JobResponse;
}

function ExportJobRow({ job }: ExportJobRowProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border p-3',
        job.status === 'failed'
          ? 'border-red-500/30 bg-red-500/5'
          : job.status === 'running'
            ? 'border-[#76B900]/30 bg-[#76B900]/5'
            : 'border-gray-700 bg-gray-800/50'
      )}
      data-testid={`export-job-${job.job_id}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getJobStatusIcon(job.status)}
          <div>
            <Text className="text-sm font-medium text-gray-200">
              {job.job_type.charAt(0).toUpperCase() + job.job_type.slice(1)} Job
            </Text>
            <Text className="text-xs text-gray-500">
              {job.started_at
                ? `Started: ${new Date(job.started_at).toLocaleTimeString()}`
                : `Created: ${new Date(job.created_at).toLocaleTimeString()}`}
            </Text>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {job.status === 'running' && job.progress !== null && (
            <div className="w-20">
              <ProgressBar value={job.progress} color="emerald" className="h-1.5" />
              <Text className="mt-0.5 text-center text-xs text-gray-400">{job.progress}%</Text>
            </div>
          )}
          <Badge color={getJobStatusColor(job.status)} size="sm">
            {job.status}
          </Badge>
        </div>
      </div>
      {job.message && (
        <Text className="mt-2 text-xs text-gray-400">{job.message}</Text>
      )}
      {job.error && (
        <div className="mt-2 rounded border border-red-500/30 bg-red-500/10 p-2">
          <Text className="text-xs text-red-400">{job.error}</Text>
        </div>
      )}
    </div>
  );
}

/**
 * Cleanup summary component - shows last cleanup info
 */
interface CleanupSummaryProps {
  cleanupStatus: CleanupStatusResponse | null;
}

function CleanupSummary({ cleanupStatus }: CleanupSummaryProps) {
  if (!cleanupStatus) {
    return null;
  }

  return (
    <div className="mb-4 rounded-lg bg-gray-800/30 p-3" data-testid="cleanup-summary">
      <Text className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
        Cleanup Service
      </Text>
      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {cleanupStatus.running ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-gray-500" />
            )}
            <Text className="text-gray-400">Status:</Text>
          </div>
          <Text className={clsx('font-medium', cleanupStatus.running ? 'text-green-400' : 'text-gray-400')}>
            {cleanupStatus.running ? 'Running' : 'Stopped'}
          </Text>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-gray-500" />
            <Text className="text-gray-400">Scheduled Time:</Text>
          </div>
          <Text className="font-medium text-white">{cleanupStatus.cleanup_time}</Text>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-500" />
            <Text className="text-gray-400">Retention:</Text>
          </div>
          <Text className="font-medium text-white">{cleanupStatus.retention_days} days</Text>
        </div>
        {cleanupStatus.next_cleanup && (
          <div className="flex items-center justify-between">
            <Text className="text-gray-400">Next Cleanup:</Text>
            <Text className="font-medium text-white">
              {new Date(cleanupStatus.next_cleanup).toLocaleString()}
            </Text>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Orphaned files warning component
 */
interface OrphanedFilesWarningProps {
  orphanedPreview: OrphanedFileCleanupResponse | null;
  onCleanOrphaned: () => void;
  isLoading: boolean;
}

function OrphanedFilesWarning({ orphanedPreview, onCleanOrphaned, isLoading }: OrphanedFilesWarningProps) {
  if (!orphanedPreview || orphanedPreview.orphaned_count === 0) {
    return null;
  }

  return (
    <div
      className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3"
      data-testid="orphaned-files-warning"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-2">
          <FileQuestion className="mt-0.5 h-4 w-4 text-amber-500" />
          <div>
            <Text className="text-sm font-medium text-amber-400">
              {formatNumber(orphanedPreview.orphaned_count)} Orphaned Files Found
            </Text>
            <Text className="text-xs text-amber-300/70">
              {orphanedPreview.total_size_formatted ?? formatBytes(orphanedPreview.total_size)} can be reclaimed
            </Text>
            <Text className="mt-1 text-xs text-gray-400">
              These files exist on disk but are not referenced in the database.
            </Text>
          </div>
        </div>
        <Button
          size="xs"
          color="amber"
          variant="secondary"
          onClick={onCleanOrphaned}
          disabled={isLoading}
          data-testid="clean-orphaned-button"
        >
          {isLoading ? 'Cleaning...' : 'Clean Up'}
        </Button>
      </div>
    </div>
  );
}

/**
 * Cleanup preview modal component
 */
interface CleanupPreviewModalProps {
  preview: CleanupResponse;
  onConfirm: () => void;
  onCancel: () => void;
  isExecuting: boolean;
}

function CleanupPreviewModal({ preview, onConfirm, onCancel, isExecuting }: CleanupPreviewModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      data-testid="cleanup-preview-modal"
    >
      <div className="mx-4 w-full max-w-md rounded-lg border border-gray-700 bg-[#1A1A1A] p-6">
        <div className="mb-4 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <Title className="text-white">Confirm Cleanup</Title>
        </div>

        <Text className="mb-4 text-sm text-gray-400">
          The following data will be permanently deleted:
        </Text>

        <div className="mb-4 space-y-2">
          <div className="flex justify-between">
            <Text className="text-sm text-gray-300">Events:</Text>
            <Text className="text-sm font-medium text-white">{formatNumber(preview.events_deleted)} events</Text>
          </div>
          <div className="flex justify-between">
            <Text className="text-sm text-gray-300">Detections:</Text>
            <Text className="text-sm font-medium text-white">{formatNumber(preview.detections_deleted)} detections</Text>
          </div>
          <div className="flex justify-between">
            <Text className="text-sm text-gray-300">GPU Stats:</Text>
            <Text className="text-sm font-medium text-white">{formatNumber(preview.gpu_stats_deleted)}</Text>
          </div>
          <div className="flex justify-between">
            <Text className="text-sm text-gray-300">Logs:</Text>
            <Text className="text-sm font-medium text-white">{formatNumber(preview.logs_deleted)}</Text>
          </div>
          <div className="flex justify-between">
            <Text className="text-sm text-gray-300">Thumbnails:</Text>
            <Text className="text-sm font-medium text-white">{formatNumber(preview.thumbnails_deleted)} files</Text>
          </div>
          {preview.space_reclaimed > 0 && (
            <div className="mt-2 flex justify-between border-t border-gray-700 pt-2">
              <Text className="text-sm font-medium text-gray-300">Space to reclaim:</Text>
              <Text className="text-sm font-medium text-[#76B900]">{formatBytes(preview.space_reclaimed)}</Text>
            </div>
          )}
        </div>

        <Text className="mb-4 text-xs text-amber-500">
          This action cannot be undone. Data older than {preview.retention_days} days will be deleted.
        </Text>

        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={onCancel}
            disabled={isExecuting}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            color="red"
            onClick={onConfirm}
            disabled={isExecuting}
            className="flex-1"
            data-testid="confirm-cleanup-button"
          >
            {isExecuting ? 'Deleting...' : 'Delete Data'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * FileOperationsPanel - Displays file operations status and storage metrics
 *
 * Shows:
 * - Storage usage (total, used, available)
 * - Storage breakdown by category (thumbnails, images, clips)
 * - Active export jobs with progress
 * - Cleanup action button with preview
 *
 * Fetches data from:
 * - GET /api/system/storage - Storage metrics
 * - GET /api/jobs - Export job status
 * - POST /api/system/cleanup - Trigger cleanup
 */
export default function FileOperationsPanel({
  pollingInterval = 30000,
  onStorageChange,
  defaultExpanded = true,
  'data-testid': testId = 'file-operations-panel',
  className,
}: FileOperationsPanelProps) {
  const [storageStats, setStorageStats] = useState<StorageStatsResponse | null>(null);
  const [jobs, setJobs] = useState<JobListResponse | null>(null);
  const [cleanupStatus, setCleanupStatus] = useState<CleanupStatusResponse | null>(null);
  const [orphanedPreview, setOrphanedPreview] = useState<OrphanedFileCleanupResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Cleanup state
  const [cleanupPreview, setCleanupPreview] = useState<CleanupResponse | null>(null);
  const [cleanupError, setCleanupError] = useState<string | null>(null);
  const [isLoadingCleanup, setIsLoadingCleanup] = useState(false);
  const [isExecutingCleanup, setIsExecutingCleanup] = useState(false);

  // Orphaned files cleanup state
  const [isLoadingOrphaned, setIsLoadingOrphaned] = useState(false);

  // Storage status store for header warning
  const updateStorageStatus = useStorageStatusStore((state) => state.update);

  const fetchData = useCallback(async () => {
    try {
      const [storageData, jobsData, cleanupStatusData, orphanedData] = await Promise.all([
        fetchStorageStats(),
        fetchJobs().catch(() => ({ items: [], pagination: { total: 0, offset: 0, limit: 50, has_more: false } })),
        fetchCleanupStatus().catch(() => null),
        previewOrphanedFiles().catch(() => null),
      ]);

      setStorageStats(storageData);
      setJobs(jobsData);
      setCleanupStatus(cleanupStatusData);
      setOrphanedPreview(orphanedData);
      setLastUpdated(new Date());
      setError(null);
      onStorageChange?.(storageData);

      // Update global storage status store for header warning
      updateStorageStatus(
        storageData.disk_usage_percent,
        storageData.disk_used_bytes,
        storageData.disk_total_bytes,
        storageData.disk_free_bytes
      );
    } catch (err) {
      console.error('Failed to fetch file operations data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [onStorageChange, updateStorageStatus]);

  // Initial fetch
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchData]);

  // Handle cleanup preview
  const handleCleanupClick = async () => {
    setCleanupError(null);
    setIsLoadingCleanup(true);

    try {
      const preview = await previewCleanup();
      setCleanupPreview(preview);
    } catch (err) {
      console.error('Failed to preview cleanup:', err);
      setCleanupError(err instanceof Error ? err.message : 'Failed to preview cleanup');
    } finally {
      setIsLoadingCleanup(false);
    }
  };

  // Handle cleanup confirmation
  const handleCleanupConfirm = async () => {
    setIsExecutingCleanup(true);

    try {
      await triggerCleanup();
      setCleanupPreview(null);
      // Refresh data after cleanup
      await fetchData();
    } catch (err) {
      console.error('Failed to execute cleanup:', err);
      setCleanupError(err instanceof Error ? err.message : 'Failed to execute cleanup');
    } finally {
      setIsExecutingCleanup(false);
    }
  };

  // Handle orphaned files cleanup
  const handleOrphanedCleanup = async () => {
    setIsLoadingOrphaned(true);
    setCleanupError(null);

    try {
      await triggerOrphanedCleanup();
      // Refresh data after cleanup
      await fetchData();
    } catch (err) {
      console.error('Failed to clean orphaned files:', err);
      setCleanupError(err instanceof Error ? err.message : 'Failed to clean orphaned files');
    } finally {
      setIsLoadingOrphaned(false);
    }
  };

  // Filter export jobs
  const exportJobs = jobs?.items.filter((job) => job.job_type === 'export') || [];
  const activeExports = exportJobs.filter((job) => job.status === 'running' || job.status === 'pending');
  const hasActiveExports = activeExports.length > 0;

  // Loading state
  if (loading) {
    return (
      <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)} data-testid="file-operations-panel-loading">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <HardDrive className="h-5 w-5 text-[#76B900]" />
          File Operations
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-gray-800" />
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !storageStats) {
    return (
      <Card className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)} data-testid="file-operations-panel-error">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <HardDrive className="h-5 w-5 text-[#76B900]" />
          File Operations
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load file operations</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  const isHighDiskUsage = storageStats && storageStats.disk_usage_percent >= 85;

  return (
    <>
      <Card
        className={clsx(
          'border-gray-800 bg-[#1A1A1A] shadow-lg',
          isHighDiskUsage && 'border-amber-500/30',
          className
        )}
        data-testid={testId}
      >
        {/* Collapsible Header */}
        <button
          type="button"
          className="flex w-full items-center justify-between text-left"
          onClick={() => setIsExpanded(!isExpanded)}
          data-testid="panel-toggle"
          aria-expanded={isExpanded}
          aria-controls="file-operations-content"
        >
          <Title className="flex items-center gap-2 text-white">
            <HardDrive className="h-5 w-5 text-[#76B900]" />
            File Operations
            {isHighDiskUsage && (
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            )}
          </Title>

          <div className="flex items-center gap-2">
            {/* Summary Badge */}
            {storageStats && (
              <Badge
                color={isHighDiskUsage ? 'yellow' : 'emerald'}
                size="sm"
              >
                {storageStats.disk_usage_percent.toFixed(1)}% Used
              </Badge>
            )}
            {hasActiveExports && (
              <Badge color="blue" size="sm">
                {activeExports.length} Active
              </Badge>
            )}
            {/* Expand/Collapse Icon */}
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-gray-400" data-testid="collapse-icon" />
            ) : (
              <ChevronDown className="h-5 w-5 text-gray-400" data-testid="expand-icon" />
            )}
          </div>
        </button>

        {/* Collapsible Content */}
        <div
          id="file-operations-content"
          className={clsx(
            'overflow-hidden transition-all duration-300 ease-in-out',
            isExpanded ? 'mt-4 max-h-[800px] opacity-100' : 'max-h-0 opacity-0'
          )}
        >
          {storageStats && (
            <>
              {/* Storage Usage Section */}
              <div className="mb-4" data-testid="storage-usage-section">
                <div className="mb-2 flex items-center justify-between">
                  <Text className="text-sm text-gray-400">Disk Usage</Text>
                  <Text className="text-sm font-medium text-white">
                    {formatBytes(storageStats.disk_used_bytes)} / {formatBytes(storageStats.disk_total_bytes)}
                  </Text>
                </div>
                <ProgressBar
                  value={storageStats.disk_usage_percent}
                  color={isHighDiskUsage ? 'yellow' : 'emerald'}
                  className="h-2"
                />
                <div className="mt-1 flex items-center justify-between">
                  <Text className="text-xs text-gray-500">
                    {formatBytes(storageStats.disk_free_bytes)} free
                  </Text>
                  <Text className={clsx('text-xs', isHighDiskUsage ? 'text-amber-500' : 'text-gray-500')}>
                    {storageStats.disk_usage_percent.toFixed(1)}%
                  </Text>
                </div>

                {/* Disk Usage Warning */}
                {isHighDiskUsage && (
                  <div
                    className="mt-2 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2"
                    data-testid="disk-usage-warning"
                  >
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    <Text className="text-xs text-amber-400">
                      Disk usage is high. Consider running cleanup to free space.
                    </Text>
                  </div>
                )}
              </div>

              {/* Storage Breakdown */}
              <div className="mb-4 space-y-2">
                <Text className="text-xs font-medium uppercase tracking-wider text-gray-500">
                  Storage Breakdown
                </Text>
                <StorageCategory
                  icon={<FileImage className="h-4 w-4 text-blue-400" />}
                  label="Thumbnails"
                  fileCount={storageStats.thumbnails.file_count}
                  sizeBytes={storageStats.thumbnails.size_bytes}
                  testId="storage-category-thumbnails"
                />
                <StorageCategory
                  icon={<Image className="h-4 w-4 text-purple-400" />}
                  label="Images"
                  fileCount={storageStats.images.file_count}
                  sizeBytes={storageStats.images.size_bytes}
                  testId="storage-category-images"
                />
                <StorageCategory
                  icon={<Film className="h-4 w-4 text-cyan-400" />}
                  label="Video Clips"
                  fileCount={storageStats.clips.file_count}
                  sizeBytes={storageStats.clips.size_bytes}
                  testId="storage-category-clips"
                />
              </div>

              {/* Database Records */}
              <div className="mb-4 rounded-lg bg-gray-800/30 p-3">
                <Text className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
                  Database Records
                </Text>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex justify-between">
                    <Text className="text-gray-400">Events:</Text>
                    <Text className="font-medium text-white">{formatNumber(storageStats.events_count)}</Text>
                  </div>
                  <div className="flex justify-between">
                    <Text className="text-gray-400">Detections:</Text>
                    <Text className="font-medium text-white">{formatNumber(storageStats.detections_count)}</Text>
                  </div>
                  <div className="flex justify-between">
                    <Text className="text-gray-400">GPU Stats:</Text>
                    <Text className="font-medium text-white">{formatNumber(storageStats.gpu_stats_count)}</Text>
                  </div>
                  <div className="flex justify-between">
                    <Text className="text-gray-400">Logs:</Text>
                    <Text className="font-medium text-white">{formatNumber(storageStats.logs_count)}</Text>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Cleanup Service Summary */}
          <CleanupSummary cleanupStatus={cleanupStatus} />

          {/* Orphaned Files Warning */}
          <OrphanedFilesWarning
            orphanedPreview={orphanedPreview}
            onCleanOrphaned={() => void handleOrphanedCleanup()}
            isLoading={isLoadingOrphaned}
          />

          {/* Active Exports Section */}
          <div className="mb-4" data-testid="active-exports-section">
            <Text className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
              Export Jobs
            </Text>
            {exportJobs.length > 0 ? (
              <div className="space-y-2">
                {exportJobs.slice(0, 5).map((job) => (
                  <ExportJobRow key={job.job_id} job={job} />
                ))}
              </div>
            ) : (
              <div
                className="flex items-center gap-2 rounded-lg bg-gray-800/50 p-3"
                data-testid="no-exports-message"
              >
                <FolderOpen className="h-4 w-4 text-gray-500" />
                <Text className="text-sm text-gray-500">No active exports</Text>
              </div>
            )}
          </div>

          {/* Cleanup Error */}
          {cleanupError && (
            <div
              className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3"
              data-testid="cleanup-error"
            >
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <Text className="text-sm text-red-400">{cleanupError}</Text>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between border-t border-gray-800 pt-4">
            <div className="flex gap-2">
              <Button
                size="xs"
                variant="secondary"
                icon={Trash2}
                onClick={() => void handleCleanupClick()}
                disabled={isLoadingCleanup}
                data-testid="cleanup-button"
              >
                {isLoadingCleanup ? 'Loading...' : 'Run Cleanup'}
              </Button>
              <Button
                size="xs"
                variant="secondary"
                icon={Download}
                disabled={hasActiveExports}
              >
                Export Data
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {lastUpdated && (
                <Text className="text-xs text-gray-500" data-testid="last-updated">
                  Last updated: {lastUpdated.toLocaleTimeString()}
                </Text>
              )}
              <button
                type="button"
                onClick={() => void fetchData()}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
                data-testid="refresh-button"
                aria-label="Refresh file operations"
              >
                <RefreshCw className={clsx('h-3 w-3', loading && 'animate-spin')} />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* Cleanup Preview Modal */}
      {cleanupPreview && (
        <CleanupPreviewModal
          preview={cleanupPreview}
          onConfirm={() => void handleCleanupConfirm()}
          onCancel={() => setCleanupPreview(null)}
          isExecuting={isExecutingCleanup}
        />
      )}
    </>
  );
}
