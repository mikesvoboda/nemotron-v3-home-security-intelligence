/**
 * ExportButton Component (NEM-1989)
 *
 * A dropdown button component for exporting events with progress tracking.
 * Supports CSV, JSON, and ZIP export formats with real-time progress updates
 * via WebSocket and polling.
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';

import Button from './common/Button';
import { useJobWebSocket } from '../hooks/useJobWebSocket';
import { logger } from '../services/logger';

// API base URL
// eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
const API_BASE: string = import.meta.env.VITE_API_URL || '';

// Export formats
type ExportFormat = 'csv' | 'json' | 'zip';

interface ExportButtonProps {
  /** Optional camera ID filter */
  cameraId?: string;
  /** Optional risk level filter */
  riskLevel?: string;
  /** Optional start date filter (ISO format) */
  startDate?: string;
  /** Optional end date filter (ISO format) */
  endDate?: string;
  /** Optional reviewed status filter */
  reviewed?: boolean;
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'outline';
  /** Button size */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
  /** Disabled state */
  disabled?: boolean;
}

interface JobStatus {
  job_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string | null;
  result?: {
    file_path: string;
    file_size: number;
    event_count: number;
    format: string;
  };
  error?: string;
}

interface StartExportResponse {
  job_id: string;
  status: string;
  message: string;
}

/**
 * Format file size for display.
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * ExportButton component with dropdown menu for format selection
 * and progress tracking for background export jobs.
 */
export function ExportButton({
  cameraId,
  riskLevel,
  startDate,
  endDate,
  reviewed,
  variant = 'secondary',
  size = 'md',
  className = '',
  disabled = false,
}: ExportButtonProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  // Subscribe to job WebSocket events
  useJobWebSocket({
    onJobProgress: (data) => {
      if (data.job_id === activeJobId) {
        setJobStatus((prev) =>
          prev
            ? {
                ...prev,
                progress: data.progress,
                status: data.status as JobStatus['status'],
              }
            : null
        );
      }
    },
    onJobCompleted: (data) => {
      if (data.job_id === activeJobId) {
        const result = data.result as JobStatus['result'];
        setJobStatus((prev) =>
          prev
            ? {
                ...prev,
                status: 'completed',
                progress: 100,
                result,
              }
            : null
        );
        if (result?.file_path) {
          setDownloadUrl(`${API_BASE}${result.file_path}`);
        }
      }
    },
    onJobFailed: (data) => {
      if (data.job_id === activeJobId) {
        setJobStatus((prev) =>
          prev
            ? {
                ...prev,
                status: 'failed',
                error: data.error,
              }
            : null
        );
      }
    },
    showToasts: false,
    invalidateQueries: false,
  });

  // Poll job status as backup
  const { data: polledStatus } = useQuery<JobStatus>({
    queryKey: ['job', activeJobId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/jobs/${activeJobId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch job status');
      }
      return response.json() as Promise<JobStatus>;
    },
    enabled: !!activeJobId && jobStatus?.status !== 'completed' && jobStatus?.status !== 'failed',
    refetchInterval: 2000, // Poll every 2 seconds
  });

  // Update job status from polling when WebSocket is slower
  useEffect(() => {
    if (polledStatus && polledStatus.job_id === activeJobId) {
      setJobStatus(polledStatus);
      if (polledStatus.status === 'completed' && polledStatus.result?.file_path) {
        setDownloadUrl(`${API_BASE}${polledStatus.result.file_path}`);
      }
    }
  }, [polledStatus, activeJobId]);

  // Start export mutation
  const startExportMutation = useMutation<StartExportResponse, Error, ExportFormat>({
    mutationFn: async (format) => {
      const body: Record<string, unknown> = { format };
      if (cameraId) body.camera_id = cameraId;
      if (riskLevel) body.risk_level = riskLevel;
      if (startDate) body.start_date = startDate;
      if (endDate) body.end_date = endDate;
      if (reviewed !== undefined) body.reviewed = reviewed;

      const response = await fetch(`${API_BASE}/api/events/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error('Failed to start export');
      }

      return response.json() as Promise<StartExportResponse>;
    },
    onSuccess: (data) => {
      setActiveJobId(data.job_id);
      setJobStatus({
        job_id: data.job_id,
        job_type: 'export',
        status: 'pending',
        progress: 0,
        message: data.message,
      });
      setDownloadUrl(null);
      setIsMenuOpen(false);
      logger.info('Export job started', { job_id: data.job_id });
    },
    onError: (error) => {
      logger.error('Failed to start export', { error: error.message });
    },
  });

  const handleExport = useCallback(
    (format: ExportFormat) => {
      startExportMutation.mutate(format);
    },
    [startExportMutation]
  );

  const handleDownload = useCallback(() => {
    if (downloadUrl) {
      window.open(downloadUrl, '_blank');
    }
  }, [downloadUrl]);

  const handleReset = useCallback(() => {
    setActiveJobId(null);
    setJobStatus(null);
    setDownloadUrl(null);
  }, []);

  const isExporting = jobStatus?.status === 'pending' || jobStatus?.status === 'running';
  const isCompleted = jobStatus?.status === 'completed';
  const isFailed = jobStatus?.status === 'failed';

  // Render progress state
  if (isExporting) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div className="flex-1 min-w-[200px]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Exporting...
            </span>
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {jobStatus.progress}%
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${jobStatus.progress}%` }}
              role="progressbar"
              aria-valuenow={jobStatus.progress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          {jobStatus.message && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
              {jobStatus.message}
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          aria-label="Cancel export"
        >
          Cancel
        </Button>
      </div>
    );
  }

  // Render completed state
  if (isCompleted && downloadUrl) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span className="text-sm">
            Export complete
            {jobStatus?.result && (
              <span className="text-gray-500 dark:text-gray-400 ml-1">
                ({jobStatus.result.event_count} events, {formatFileSize(jobStatus.result.file_size)})
              </span>
            )}
          </span>
        </div>
        <Button
          variant="primary"
          size={size}
          onClick={handleDownload}
          leftIcon={
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          }
        >
          Download
        </Button>
        <Button variant="ghost" size="sm" onClick={handleReset} aria-label="New export">
          New Export
        </Button>
      </div>
    );
  }

  // Render failed state
  if (isFailed) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          <span className="text-sm">
            Export failed
            {jobStatus?.error && (
              <span className="text-gray-500 dark:text-gray-400 ml-1">
                ({jobStatus.error})
              </span>
            )}
          </span>
        </div>
        <Button variant="secondary" size={size} onClick={handleReset}>
          Try Again
        </Button>
      </div>
    );
  }

  // Render default state with dropdown
  return (
    <div className={`relative ${className}`}>
      <Button
        variant={variant}
        size={size}
        onClick={() => setIsMenuOpen(!isMenuOpen)}
        disabled={disabled || startExportMutation.isPending}
        isLoading={startExportMutation.isPending}
        rightIcon={
          <svg
            className={`w-4 h-4 transition-transform ${isMenuOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        }
        aria-expanded={isMenuOpen}
        aria-haspopup="menu"
      >
        Export
      </Button>

      {isMenuOpen && (
        <>
          {/* Backdrop to close menu */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Dropdown menu */}
          <div
            className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-20"
            role="menu"
            aria-orientation="vertical"
          >
            <div className="py-1">
              <button
                type="button"
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                onClick={() => handleExport('csv')}
                role="menuitem"
              >
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                Export as CSV
              </button>
              <button
                type="button"
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                onClick={() => handleExport('json')}
                role="menuitem"
              >
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                  />
                </svg>
                Export as JSON
              </button>
              <button
                type="button"
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                onClick={() => handleExport('zip')}
                role="menuitem"
              >
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
                  />
                </svg>
                Export as ZIP
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default ExportButton;
