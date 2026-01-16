import { Card, Title, Text, Badge, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  PlayCircle,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Layers,
  Zap,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchTelemetry,
  fetchDlqStats,
  fetchReadiness,
  type WorkerStatus,
} from '../../services/api';

/**
 * Status of a background job
 */
export type JobStatus = 'running' | 'completed' | 'failed' | 'pending';

/**
 * Represents a background job in the system
 */
export interface BackgroundJob {
  /** Unique identifier for the job */
  id: string;
  /** Human-readable name */
  name: string;
  /** Current status */
  status: JobStatus;
  /** Job type/category */
  type: 'detection' | 'analysis' | 'cleanup' | 'batch' | 'system';
  /** Progress percentage (0-100), null if not applicable */
  progress: number | null;
  /** When the job started */
  startedAt: string | null;
  /** When the job completed (if completed) */
  completedAt: string | null;
  /** Error message if failed */
  error: string | null;
  /** Additional details about the job */
  details?: Record<string, unknown>;
}

/**
 * Props for BackgroundJobsPanel component
 */
export interface BackgroundJobsPanelProps {
  /** Polling interval in milliseconds (default: 10000) */
  pollingInterval?: number;
  /** Optional callback when jobs change */
  onJobsChange?: (jobs: BackgroundJob[]) => void;
  /** Whether the panel starts expanded (default: true) */
  defaultExpanded?: boolean;
  /** Maximum number of jobs to display (default: 10) */
  maxJobs?: number;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
  /** Optional className for styling */
  className?: string;
}

/**
 * Helper to get status icon and color
 */
function getStatusConfig(status: JobStatus): {
  icon: React.ReactNode;
  color: string;
  badgeColor: 'green' | 'yellow' | 'red' | 'gray';
  label: string;
} {
  switch (status) {
    case 'running':
      return {
        icon: <PlayCircle className="h-4 w-4 text-[#76B900]" />,
        color: 'text-[#76B900]',
        badgeColor: 'green',
        label: 'Running',
      };
    case 'completed':
      return {
        icon: <CheckCircle className="h-4 w-4 text-green-500" />,
        color: 'text-green-500',
        badgeColor: 'green',
        label: 'Completed',
      };
    case 'failed':
      return {
        icon: <XCircle className="h-4 w-4 text-red-500" />,
        color: 'text-red-500',
        badgeColor: 'red',
        label: 'Failed',
      };
    case 'pending':
    default:
      return {
        icon: <Clock className="h-4 w-4 text-gray-500" />,
        color: 'text-gray-500',
        badgeColor: 'gray',
        label: 'Pending',
      };
  }
}

/**
 * Helper to get job type icon
 */
function getTypeIcon(type: BackgroundJob['type']): React.ReactNode {
  switch (type) {
    case 'detection':
      return <Zap className="h-3.5 w-3.5 text-blue-400" />;
    case 'analysis':
      return <Layers className="h-3.5 w-3.5 text-purple-400" />;
    case 'cleanup':
      return <RefreshCw className="h-3.5 w-3.5 text-amber-400" />;
    case 'batch':
      return <Layers className="h-3.5 w-3.5 text-cyan-400" />;
    case 'system':
    default:
      return <Clock className="h-3.5 w-3.5 text-gray-400" />;
  }
}

/**
 * Single job row component
 */
interface JobRowProps {
  job: BackgroundJob;
  expanded: boolean;
  onToggle: () => void;
}

function JobRow({ job, expanded, onToggle }: JobRowProps) {
  const statusConfig = getStatusConfig(job.status);

  return (
    <div
      className={clsx(
        'rounded-lg border transition-all',
        job.status === 'failed'
          ? 'border-red-500/30 bg-red-500/5'
          : job.status === 'running'
            ? 'border-[#76B900]/30 bg-[#76B900]/5'
            : 'border-gray-700 bg-gray-800/50'
      )}
      data-testid={`job-row-${job.id}`}
    >
      {/* Job Header */}
      <button
        type="button"
        className="flex w-full items-center justify-between p-3 text-left"
        onClick={onToggle}
        aria-expanded={expanded}
        data-testid={`job-toggle-${job.id}`}
      >
        <div className="flex items-center gap-3">
          {/* Status Icon */}
          {statusConfig.icon}

          {/* Job Info */}
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              {getTypeIcon(job.type)}
              <Text className="text-sm font-medium text-gray-200">{job.name}</Text>
            </div>
            {job.startedAt && (
              <Text className="text-xs text-gray-500">
                Started: {new Date(job.startedAt).toLocaleTimeString()}
              </Text>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Progress Bar (if applicable) */}
          {job.progress !== null && job.status === 'running' && (
            <div className="w-24">
              <ProgressBar value={job.progress} color="emerald" className="h-1.5" />
            </div>
          )}

          {/* Status Badge */}
          <Badge color={statusConfig.badgeColor} size="sm">
            {statusConfig.label}
          </Badge>

          {/* Expand Icon */}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div
          className="border-t border-gray-700 px-3 pb-3 pt-2"
          data-testid={`job-details-${job.id}`}
        >
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <Text className="text-gray-500">Job ID:</Text>
              <Text className="font-mono text-gray-300">{job.id}</Text>
            </div>
            <div>
              <Text className="text-gray-500">Type:</Text>
              <Text className="capitalize text-gray-300">{job.type}</Text>
            </div>
            {job.completedAt && (
              <div>
                <Text className="text-gray-500">Completed:</Text>
                <Text className="text-gray-300">
                  {new Date(job.completedAt).toLocaleTimeString()}
                </Text>
              </div>
            )}
            {job.progress !== null && (
              <div>
                <Text className="text-gray-500">Progress:</Text>
                <Text className="text-gray-300">{job.progress}%</Text>
              </div>
            )}
          </div>

          {/* Error Message */}
          {job.error && (
            <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2">
              <Text className="text-xs text-red-400">{job.error}</Text>
            </div>
          )}

          {/* Additional Details */}
          {job.details && Object.keys(job.details).length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-400">
                View details
              </summary>
              <pre className="mt-1 overflow-x-auto rounded bg-gray-900 p-2 text-xs text-gray-400">
                {JSON.stringify(job.details, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * BackgroundJobsPanel - Displays background job status and history
 *
 * Shows:
 * - Active jobs in processing queues (detection, analysis)
 * - Failed jobs from DLQ
 * - Worker status
 * - Progress indicators
 * - Expandable job details
 *
 * Fetches data from:
 * - GET /api/system/telemetry - Queue depths
 * - GET /api/dlq/stats - Failed jobs count
 * - GET /api/system/health/ready - Worker status
 */
export default function BackgroundJobsPanel({
  pollingInterval = 10000,
  onJobsChange,
  defaultExpanded = true,
  maxJobs = 10,
  'data-testid': testId = 'background-jobs-panel',
  className,
}: BackgroundJobsPanelProps) {
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [expandedJobIds, setExpandedJobIds] = useState<Set<string>>(new Set());

  const fetchJobsData = useCallback(async () => {
    try {
      const [telemetry, dlqStats, readiness] = await Promise.all([
        fetchTelemetry().catch(() => null),
        fetchDlqStats().catch(() => null),
        fetchReadiness().catch(() => null),
      ]);

      const newJobs: BackgroundJob[] = [];
      const now = new Date().toISOString();

      // Add detection queue jobs
      if (
        telemetry?.queues?.detection_queue !== undefined &&
        telemetry.queues.detection_queue > 0
      ) {
        newJobs.push({
          id: 'detection-queue',
          name: 'Detection Processing',
          status: 'running',
          type: 'detection',
          progress: null,
          startedAt: now,
          completedAt: null,
          error: null,
          details: {
            pending_jobs: telemetry.queues.detection_queue,
            avg_latency_ms: telemetry.latencies?.detect?.avg_ms ?? null,
          },
        });
      }

      // Add analysis queue jobs
      if (telemetry?.queues?.analysis_queue !== undefined && telemetry.queues.analysis_queue > 0) {
        newJobs.push({
          id: 'analysis-queue',
          name: 'Analysis Processing',
          status: 'running',
          type: 'analysis',
          progress: null,
          startedAt: now,
          completedAt: null,
          error: null,
          details: {
            pending_jobs: telemetry.queues.analysis_queue,
            avg_latency_ms: telemetry.latencies?.analyze?.avg_ms ?? null,
          },
        });
      }

      // Add failed jobs from DLQ
      if (dlqStats) {
        if (dlqStats.detection_queue_count > 0) {
          newJobs.push({
            id: 'dlq-detection',
            name: 'Failed Detection Jobs',
            status: 'failed',
            type: 'detection',
            progress: null,
            startedAt: null,
            completedAt: null,
            error: `${dlqStats.detection_queue_count} jobs failed and moved to dead letter queue`,
            details: {
              failed_count: dlqStats.detection_queue_count,
            },
          });
        }

        if (dlqStats.analysis_queue_count > 0) {
          newJobs.push({
            id: 'dlq-analysis',
            name: 'Failed Analysis Jobs',
            status: 'failed',
            type: 'analysis',
            progress: null,
            startedAt: null,
            completedAt: null,
            error: `${dlqStats.analysis_queue_count} jobs failed and moved to dead letter queue`,
            details: {
              failed_count: dlqStats.analysis_queue_count,
            },
          });
        }
      }

      // Add worker status as jobs
      if (readiness?.workers) {
        readiness.workers.forEach((worker: WorkerStatus) => {
          // Only show relevant workers as "jobs"
          if (
            [
              'detection_worker',
              'analysis_worker',
              'batch_timeout_worker',
              'cleanup_service',
            ].includes(worker.name)
          ) {
            const workerType = worker.name.includes('detection')
              ? 'detection'
              : worker.name.includes('analysis')
                ? 'analysis'
                : worker.name.includes('batch')
                  ? 'batch'
                  : 'cleanup';

            newJobs.push({
              id: `worker-${worker.name}`,
              name: worker.name
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(' '),
              status: worker.running ? 'running' : 'failed',
              type: workerType,
              progress: null,
              startedAt: worker.running ? now : null,
              completedAt: null,
              error: worker.running ? null : (worker.message ?? 'Worker is not running'),
              details: {
                worker_status: worker.running ? 'active' : 'stopped',
              },
            });
          }
        });
      }

      // If no jobs at all, add an idle job
      if (newJobs.length === 0) {
        newJobs.push({
          id: 'idle',
          name: 'System Idle',
          status: 'completed',
          type: 'system',
          progress: 100,
          startedAt: now,
          completedAt: now,
          error: null,
          details: {
            message: 'No active background processing',
          },
        });
      }

      // Sort: failed first, then running, then completed
      newJobs.sort((a, b) => {
        const priority = { failed: 0, running: 1, pending: 2, completed: 3 };
        return priority[a.status] - priority[b.status];
      });

      // Limit to maxJobs
      const limitedJobs = newJobs.slice(0, maxJobs);

      setJobs(limitedJobs);
      setLastUpdated(new Date());
      setError(null);
      onJobsChange?.(limitedJobs);
    } catch (err) {
      console.error('Failed to fetch background jobs:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch job data');
    } finally {
      setLoading(false);
    }
  }, [maxJobs, onJobsChange]);

  // Initial fetch
  useEffect(() => {
    void fetchJobsData();
  }, [fetchJobsData]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchJobsData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchJobsData]);

  // Toggle job expansion
  const toggleJobExpansion = (jobId: string) => {
    setExpandedJobIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(jobId)) {
        newSet.delete(jobId);
      } else {
        newSet.add(jobId);
      }
      return newSet;
    });
  };

  // Calculate summary stats
  const runningCount = jobs.filter((j) => j.status === 'running').length;
  const failedCount = jobs.filter((j) => j.status === 'failed').length;
  const completedCount = jobs.filter((j) => j.status === 'completed').length;

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="background-jobs-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Layers className="h-5 w-5 text-[#76B900]" />
          Background Jobs
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800" />
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error && jobs.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="background-jobs-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Layers className="h-5 w-5 text-[#76B900]" />
          Background Jobs
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load job status</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        failedCount > 0 && 'border-red-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Collapsible Header */}
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="jobs-panel-toggle"
        aria-expanded={isExpanded}
        aria-controls="jobs-list-content"
      >
        <Title className="flex items-center gap-2 text-white">
          <Layers className="h-5 w-5 text-[#76B900]" />
          Background Jobs
          {failedCount > 0 && (
            <AlertTriangle
              className="h-4 w-4 text-red-500"
              data-testid="jobs-warning-icon"
              aria-label="Failed jobs present"
            />
          )}
        </Title>

        <div className="flex items-center gap-2">
          {/* Summary Badges */}
          {failedCount > 0 && (
            <Badge color="red" size="sm" data-testid="failed-count-badge">
              {failedCount} Failed
            </Badge>
          )}
          {runningCount > 0 && (
            <Badge color="green" size="sm" data-testid="running-count-badge">
              {runningCount} Running
            </Badge>
          )}
          {runningCount === 0 && failedCount === 0 && completedCount > 0 && (
            <Badge color="gray" size="sm" data-testid="idle-badge">
              Idle
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
        id="jobs-list-content"
        className={clsx(
          'overflow-hidden transition-all duration-300 ease-in-out',
          isExpanded ? 'mt-4 max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
        )}
        data-testid="jobs-list-content"
      >
        {/* Jobs List */}
        <div className="space-y-2" data-testid="jobs-list">
          {jobs.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              expanded={expandedJobIds.has(job.id)}
              onToggle={() => toggleJobExpansion(job.id)}
            />
          ))}
        </div>

        {/* Last Updated */}
        {lastUpdated && (
          <div className="mt-4 flex items-center justify-between border-t border-gray-800 pt-3">
            <Text className="text-xs text-gray-500" data-testid="last-updated">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Text>
            <button
              type="button"
              onClick={() => void fetchJobsData()}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
              data-testid="refresh-button"
              aria-label="Refresh job status"
            >
              <RefreshCw className={clsx('h-3 w-3', loading && 'animate-spin')} />
              Refresh
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
