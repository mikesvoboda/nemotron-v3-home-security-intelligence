/**
 * ExportProgress Component
 *
 * Displays real-time progress for background export jobs with:
 * - Progress bar with percentage
 * - Current step label
 * - Items processed count
 * - Estimated time remaining
 * - Cancel button
 * - Download button when complete
 *
 * @see NEM-2386
 */

import { ProgressBar, Button, Card } from '@tremor/react';
import {
  AlertCircle,
  Check,
  Download,
  FileSpreadsheet,
  Loader2,
  X,
} from 'lucide-react';
import { useEffect, useState, useCallback, useRef } from 'react';

import {
  getExportStatus,
  cancelExportJob,
  downloadExportFile,
} from '../../services/api';
import {
  isExportJobComplete,
  isExportJobRunning,
  isExportJobFailed,
  formatFileSize,
  calculateTimeRemaining,
} from '../../types/export';

import type { ExportJob } from '../../types/export';

export interface ExportProgressProps {
  /** Export job ID to track */
  jobId: string;
  /** Callback when export completes successfully */
  onComplete?: (downloadUrl: string) => void;
  /** Callback when export is cancelled */
  onCancel?: () => void;
  /** Callback when export fails */
  onError?: (error: string) => void;
  /** Polling interval in milliseconds (default: 1000) */
  pollingInterval?: number;
  /** Whether to show compact version */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Export progress tracking component.
 *
 * Polls the export status endpoint and displays real-time progress.
 * Supports cancellation and automatic download when complete.
 */
export default function ExportProgress({
  jobId,
  onComplete,
  onCancel,
  onError,
  pollingInterval = 1000,
  compact = false,
  className = '',
}: ExportProgressProps) {
  const [job, setJob] = useState<ExportJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  // Track if component is mounted to prevent state updates after unmount
  const mountedRef = useRef(true);

  // Fetch export status
  const fetchStatus = useCallback(async () => {
    try {
      const status = await getExportStatus(jobId);
      if (mountedRef.current) {
        setJob(status);
        setLoading(false);

        // Notify parent on completion
        if (status.status === 'completed' && onComplete && status.result?.output_path) {
          onComplete(status.result.output_path);
        }

        // Notify parent on failure
        if (status.status === 'failed' && onError) {
          onError(status.error_message || 'Export failed');
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        const message = err instanceof Error ? err.message : 'Failed to fetch export status';
        setError(message);
        setLoading(false);
        if (onError) {
          onError(message);
        }
      }
    }
  }, [jobId, onComplete, onError]);

  // Poll for status updates while job is active
  useEffect(() => {
    mountedRef.current = true;

    // Initial fetch
    void fetchStatus();

    // Set up polling
    const intervalId = setInterval(() => {
      if (job && !isExportJobComplete(job)) {
        void fetchStatus();
      }
    }, pollingInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchStatus, job, pollingInterval]);

  // Stop polling when job completes
  useEffect(() => {
    if (job && isExportJobComplete(job)) {
      // Job is done, no more polling needed
    }
  }, [job]);

  // Handle cancel
  const handleCancel = async () => {
    if (!showCancelConfirm) {
      setShowCancelConfirm(true);
      return;
    }

    setCancelling(true);
    try {
      await cancelExportJob(jobId);
      setShowCancelConfirm(false);
      if (onCancel) {
        onCancel();
      }
      // Refresh status
      await fetchStatus();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel export';
      setError(message);
    } finally {
      setCancelling(false);
    }
  };

  // Handle download
  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadExportFile(jobId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to download export';
      setError(message);
    } finally {
      setDownloading(false);
    }
  };

  // Render loading state
  if (loading) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
        <span className="text-sm text-gray-500">Loading export status...</span>
      </div>
    );
  }

  // Render error state
  if (error && !job) {
    return (
      <div className={`flex items-center gap-2 text-red-500 ${className}`}>
        <AlertCircle className="h-4 w-4" />
        <span className="text-sm">{error}</span>
      </div>
    );
  }

  // No job found
  if (!job) {
    return null;
  }

  const { progress, status, export_format, error_message } = job;
  const isRunning = isExportJobRunning(job);
  const isFailed = isExportJobFailed(job);
  const isComplete = status === 'completed';
  const timeRemaining = calculateTimeRemaining(job.started_at, progress.progress_percent);

  // Compact version
  if (compact) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        {isRunning && (
          <>
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            <ProgressBar value={progress.progress_percent} className="w-24" />
            <span className="text-sm text-gray-500">{progress.progress_percent}%</span>
          </>
        )}
        {isComplete && (
          <>
            <Check className="h-4 w-4 text-green-500" />
            <Button
              size="xs"
              variant="secondary"
              icon={Download}
              onClick={() => void handleDownload()}
              loading={downloading}
            >
              Download
            </Button>
          </>
        )}
        {isFailed && (
          <>
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm text-red-500">Failed</span>
          </>
        )}
      </div>
    );
  }

  // Full version
  return (
    <Card className={`p-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-gray-500" />
          <span className="font-medium">
            {export_format.toUpperCase()} Export
          </span>
        </div>
        {isRunning && !showCancelConfirm && (
          <Button
            size="xs"
            variant="secondary"
            icon={X}
            onClick={() => void handleCancel()}
            disabled={cancelling}
          >
            Cancel
          </Button>
        )}
        {showCancelConfirm && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Cancel export?</span>
            <Button
              size="xs"
              variant="secondary"
              onClick={() => setShowCancelConfirm(false)}
            >
              No
            </Button>
            <Button
              size="xs"
              color="red"
              onClick={() => void handleCancel()}
              loading={cancelling}
            >
              Yes
            </Button>
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between mb-1">
          <span className="text-sm text-gray-500">
            {progress.current_step || (isRunning ? 'Processing...' : status)}
          </span>
          <span className="text-sm font-medium">
            {progress.progress_percent}%
          </span>
        </div>
        <ProgressBar
          value={progress.progress_percent}
          color={isFailed ? 'red' : isComplete ? 'green' : 'blue'}
        />
      </div>

      {/* Details */}
      <div className="flex flex-wrap gap-4 text-sm text-gray-500">
        {/* Items processed */}
        {progress.total_items !== null && (
          <div>
            {progress.processed_items.toLocaleString()} / {progress.total_items.toLocaleString()} items
          </div>
        )}

        {/* Time remaining */}
        {isRunning && timeRemaining && (
          <div>{timeRemaining}</div>
        )}

        {/* File size (when complete) */}
        {isComplete && job.result?.output_size_bytes && (
          <div>{formatFileSize(job.result.output_size_bytes)}</div>
        )}

        {/* Duration (when complete) */}
        {isComplete && job.started_at && job.completed_at && (
          <div>
            Completed in {Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)}s
          </div>
        )}
      </div>

      {/* Error message */}
      {isFailed && error_message && (
        <div className="mt-3 flex items-center gap-2 text-red-500 text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>{error_message}</span>
        </div>
      )}

      {/* Download button */}
      {isComplete && (
        <div className="mt-4">
          <Button
            icon={Download}
            onClick={() => void handleDownload()}
            loading={downloading}
          >
            Download {export_format.toUpperCase()}
          </Button>
        </div>
      )}

      {/* Local error display */}
      {error && (
        <div className="mt-3 flex items-center gap-2 text-red-500 text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}
    </Card>
  );
}
