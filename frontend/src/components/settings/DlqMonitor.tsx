import { Card, Title, Text, Button, Badge } from '@tremor/react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Trash2,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchDlqStats,
  fetchDlqJobs,
  requeueAllDlqJobs,
  clearDlq,
  type DLQQueueName,
  type DLQStatsResponse,
  type DLQJobResponse,
} from '../../services/api';

export interface DlqMonitorProps {
  className?: string;
  /** Polling interval in milliseconds. Set to 0 to disable auto-refresh. Default: 30000 (30s) */
  refreshInterval?: number;
}

interface QueueState {
  expanded: boolean;
  jobs: DLQJobResponse[] | null;
  loading: boolean;
  error: string | null;
}

interface ConfirmationState {
  action: 'requeue' | 'clear' | null;
  queueName: DLQQueueName | null;
}

/**
 * DLQ Monitor component for viewing and managing failed jobs in dead-letter queues.
 *
 * Features:
 * - Badge showing total failed job count
 * - Expandable panels for each queue
 * - Job details with error messages and timestamps
 * - Requeue all and clear buttons with confirmation
 * - Auto-refresh capability
 */
export default function DlqMonitor({ className, refreshInterval = 30000 }: DlqMonitorProps) {
  const [stats, setStats] = useState<DLQStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<{ success: boolean; message: string } | null>(
    null
  );
  const [confirmation, setConfirmation] = useState<ConfirmationState>({
    action: null,
    queueName: null,
  });

  const [queues, setQueues] = useState<Record<DLQQueueName, QueueState>>({
    'dlq:detection_queue': { expanded: false, jobs: null, loading: false, error: null },
    'dlq:analysis_queue': { expanded: false, jobs: null, loading: false, error: null },
  });

  const loadStats = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchDlqStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load DLQ stats');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval <= 0) return;

    const interval = setInterval(() => {
      void loadStats();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, loadStats]);

  const loadQueueJobs = async (queueName: DLQQueueName) => {
    setQueues((prev) => ({
      ...prev,
      [queueName]: { ...prev[queueName], loading: true, error: null },
    }));

    try {
      const data = await fetchDlqJobs(queueName);
      setQueues((prev) => ({
        ...prev,
        [queueName]: { ...prev[queueName], jobs: data.jobs, loading: false },
      }));
    } catch (err) {
      setQueues((prev) => ({
        ...prev,
        [queueName]: {
          ...prev[queueName],
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load jobs',
        },
      }));
    }
  };

  const toggleQueue = async (queueName: DLQQueueName) => {
    const isExpanded = queues[queueName].expanded;

    setQueues((prev) => ({
      ...prev,
      [queueName]: { ...prev[queueName], expanded: !isExpanded },
    }));

    // Load jobs when expanding if not already loaded
    if (!isExpanded && queues[queueName].jobs === null) {
      await loadQueueJobs(queueName);
    }
  };

  const handleRequeueAll = async (queueName: DLQQueueName) => {
    setActionLoading(true);
    setActionResult(null);
    setConfirmation({ action: null, queueName: null });

    try {
      const result = await requeueAllDlqJobs(queueName);
      setActionResult({ success: result.success, message: result.message });

      // Refresh stats and jobs after requeue
      await loadStats();
      if (queues[queueName].expanded) {
        await loadQueueJobs(queueName);
      }
    } catch (err) {
      setActionResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to requeue jobs',
      });
    } finally {
      setActionLoading(false);
      // Clear result after 5 seconds
      setTimeout(() => setActionResult(null), 5000);
    }
  };

  const handleClear = async (queueName: DLQQueueName) => {
    setActionLoading(true);
    setActionResult(null);
    setConfirmation({ action: null, queueName: null });

    try {
      const result = await clearDlq(queueName);
      setActionResult({ success: result.success, message: result.message });

      // Refresh stats and jobs after clear
      await loadStats();
      if (queues[queueName].expanded) {
        await loadQueueJobs(queueName);
      }
    } catch (err) {
      setActionResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to clear queue',
      });
    } finally {
      setActionLoading(false);
      // Clear result after 5 seconds
      setTimeout(() => setActionResult(null), 5000);
    }
  };

  const formatTimestamp = (isoTimestamp: string) => {
    try {
      return new Date(isoTimestamp).toLocaleString();
    } catch {
      return isoTimestamp;
    }
  };

  const getQueueDisplayName = (queueName: DLQQueueName) => {
    return queueName === 'dlq:detection_queue' ? 'Detection Queue' : 'Analysis Queue';
  };

  const getQueueCount = (queueName: DLQQueueName) => {
    if (!stats) return 0;
    return queueName === 'dlq:detection_queue'
      ? stats.detection_queue_count
      : stats.analysis_queue_count;
  };

  const totalFailedJobs = stats?.total_count ?? 0;

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <Title className="text-white">Dead Letter Queue</Title>
          {totalFailedJobs > 0 && (
            <Badge color="red" data-testid="dlq-total-badge">
              {totalFailedJobs} failed
            </Badge>
          )}
        </div>
        <Button
          variant="secondary"
          size="xs"
          onClick={() => void loadStats()}
          disabled={loading}
          className="text-gray-400 hover:text-white"
          aria-label="Refresh DLQ stats"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {loading && !stats && (
        <div className="space-y-3">
          <div className="skeleton h-12 w-full rounded-lg"></div>
          <div className="skeleton h-12 w-full rounded-lg"></div>
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {actionResult && (
        <div
          className={`mb-4 flex items-center gap-2 rounded-lg border p-4 ${
            actionResult.success
              ? 'border-green-500/30 bg-green-500/10'
              : 'border-red-500/30 bg-red-500/10'
          }`}
        >
          <AlertCircle
            className={`h-5 w-5 flex-shrink-0 ${actionResult.success ? 'text-green-500' : 'text-red-500'}`}
          />
          <Text className={actionResult.success ? 'text-green-500' : 'text-red-500'}>
            {actionResult.message}
          </Text>
        </div>
      )}

      {!loading && stats && totalFailedJobs === 0 && !error && (
        <div className="flex items-center justify-center py-8 text-gray-500">
          <Text>No failed jobs in queue</Text>
        </div>
      )}

      {stats && (
        <div className="space-y-3">
          {(['dlq:detection_queue', 'dlq:analysis_queue'] as DLQQueueName[]).map((queueName) => {
            const count = getQueueCount(queueName);
            const queueState = queues[queueName];

            if (count === 0 && !queueState.expanded) return null;

            return (
              <div
                key={queueName}
                className="overflow-hidden rounded-lg border border-gray-700"
                data-testid={`dlq-queue-${queueName}`}
              >
                {/* Queue Header */}
                <button
                  onClick={() => void toggleQueue(queueName)}
                  className="flex w-full items-center justify-between bg-gray-800/50 p-3 text-left transition-colors hover:bg-gray-800"
                  aria-expanded={queueState.expanded}
                  aria-label={`Toggle ${getQueueDisplayName(queueName)} details`}
                >
                  <div className="flex items-center gap-2">
                    {queueState.expanded ? (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                    <Text className="font-medium text-white">{getQueueDisplayName(queueName)}</Text>
                    {count > 0 && (
                      <Badge color="amber" size="sm">
                        {count}
                      </Badge>
                    )}
                  </div>
                </button>

                {/* Expanded Content */}
                {queueState.expanded && (
                  <div className="border-t border-gray-700 p-3">
                    {/* Actions */}
                    {count > 0 && (
                      <div className="mb-4 flex gap-2">
                        {confirmation.action === 'requeue' &&
                        confirmation.queueName === queueName ? (
                          <div className="flex items-center gap-2">
                            <Text className="text-sm text-amber-400">
                              Requeue all {count} jobs?
                            </Text>
                            <Button
                              size="xs"
                              className="bg-amber-600 hover:bg-amber-700"
                              onClick={() => void handleRequeueAll(queueName)}
                              disabled={actionLoading}
                            >
                              Confirm
                            </Button>
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={() => setConfirmation({ action: null, queueName: null })}
                              disabled={actionLoading}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : confirmation.action === 'clear' &&
                          confirmation.queueName === queueName ? (
                          <div className="flex items-center gap-2">
                            <Text className="text-sm text-red-400">
                              Permanently delete all {count} jobs?
                            </Text>
                            <Button
                              size="xs"
                              className="bg-red-700 hover:bg-red-800"
                              onClick={() => void handleClear(queueName)}
                              disabled={actionLoading}
                            >
                              Confirm
                            </Button>
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={() => setConfirmation({ action: null, queueName: null })}
                              disabled={actionLoading}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <>
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={() => setConfirmation({ action: 'requeue', queueName })}
                              disabled={actionLoading}
                              className="border-amber-400/30 text-amber-400 hover:bg-amber-500/10"
                            >
                              <RefreshCw className="mr-1 h-3 w-3" />
                              Requeue All
                            </Button>
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={() => setConfirmation({ action: 'clear', queueName })}
                              disabled={actionLoading}
                              className="border-red-400/30 text-red-400 hover:bg-red-500/10"
                            >
                              <Trash2 className="mr-1 h-3 w-3" />
                              Clear All
                            </Button>
                          </>
                        )}
                      </div>
                    )}

                    {/* Loading Jobs */}
                    {queueState.loading && (
                      <div className="space-y-2">
                        <div className="skeleton h-20 w-full rounded-lg"></div>
                        <div className="skeleton h-20 w-full rounded-lg"></div>
                      </div>
                    )}

                    {/* Error Loading Jobs */}
                    {queueState.error && (
                      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                        <AlertCircle className="h-4 w-4 text-red-500" />
                        <Text className="text-sm text-red-500">{queueState.error}</Text>
                      </div>
                    )}

                    {/* Empty State */}
                    {!queueState.loading &&
                      !queueState.error &&
                      queueState.jobs &&
                      queueState.jobs.length === 0 && (
                        <Text className="py-4 text-center text-gray-500">No jobs in queue</Text>
                      )}

                    {/* Job List */}
                    {!queueState.loading && !queueState.error && queueState.jobs && (
                      <div className="max-h-[400px] space-y-2 overflow-y-auto">
                        {queueState.jobs.map((job, index) => (
                          <div
                            key={`${job.queue_name}-${index}`}
                            className="rounded-lg border border-gray-700/50 bg-gray-800/30 p-3"
                            data-testid={`dlq-job-${index}`}
                          >
                            {/* Error Message */}
                            <div className="mb-2">
                              <Text className="break-all font-mono text-sm text-red-400">
                                {job.error}
                              </Text>
                            </div>

                            {/* Job Metadata */}
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                              <div className="flex items-center gap-1">
                                <RefreshCw className="h-3 w-3" />
                                <span>Attempts: {job.attempt_count}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                <span>First: {formatTimestamp(job.first_failed_at)}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                <span>Last: {formatTimestamp(job.last_failed_at)}</span>
                              </div>
                            </div>

                            {/* Original Job Payload (collapsed by default) */}
                            <details className="mt-2">
                              <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-400">
                                View payload
                              </summary>
                              <pre className="mt-1 overflow-x-auto rounded bg-gray-900 p-2 text-xs text-gray-400">
                                {JSON.stringify(job.original_job, null, 2)}
                              </pre>
                            </details>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Footer Info */}
      <div className="mt-4 border-t border-gray-800 pt-4">
        <Text className="text-xs text-gray-500">
          Dead Letter Queue stores failed processing jobs for inspection and retry. Jobs are moved
          here after exhausting retry attempts.
        </Text>
      </div>
    </Card>
  );
}
