import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { CheckCircle, XCircle, Cpu, AlertTriangle } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { fetchReadiness, type WorkerStatus } from '../../services/api';

/**
 * Props for WorkerStatusPanel component
 */
export interface WorkerStatusPanelProps {
  /** Polling interval in milliseconds (default: 10000) */
  pollingInterval?: number;
  /** Optional callback when worker status changes */
  onStatusChange?: (workers: WorkerStatus[]) => void;
}

/**
 * List of critical workers that require special highlighting.
 * These workers are essential for the AI processing pipeline.
 */
const CRITICAL_WORKERS = ['detection_worker', 'analysis_worker'];

/**
 * Human-readable names for workers
 */
const WORKER_DISPLAY_NAMES: Record<string, string> = {
  gpu_monitor: 'GPU Monitor',
  cleanup_service: 'Cleanup Service',
  system_broadcaster: 'System Broadcaster',
  file_watcher: 'File Watcher',
  detection_worker: 'Detection Worker',
  analysis_worker: 'Analysis Worker',
  batch_timeout_worker: 'Batch Timeout Worker',
  metrics_worker: 'Metrics Worker',
};

/**
 * Descriptions for each worker's function
 */
const WORKER_DESCRIPTIONS: Record<string, string> = {
  gpu_monitor: 'Monitors GPU utilization and temperature',
  cleanup_service: 'Removes old data based on retention policy',
  system_broadcaster: 'Broadcasts system status via WebSocket',
  file_watcher: 'Watches for new camera images',
  detection_worker: 'Processes images through RT-DETRv2',
  analysis_worker: 'Analyzes detections with Nemotron LLM',
  batch_timeout_worker: 'Handles batch processing timeouts',
  metrics_worker: 'Collects and reports pipeline metrics',
};

/**
 * Gets display name for a worker
 */
function getWorkerDisplayName(name: string): string {
  return WORKER_DISPLAY_NAMES[name] || name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Gets description for a worker
 */
function getWorkerDescription(name: string): string {
  return WORKER_DESCRIPTIONS[name] || 'Background worker';
}

/**
 * Checks if a worker is critical
 */
function isCriticalWorker(name: string): boolean {
  return CRITICAL_WORKERS.includes(name);
}

/**
 * WorkerStatusRow - Displays a single worker's status
 */
interface WorkerStatusRowProps {
  worker: WorkerStatus;
}

function WorkerStatusRow({ worker }: WorkerStatusRowProps) {
  const isCritical = isCriticalWorker(worker.name);
  const displayName = getWorkerDisplayName(worker.name);
  const description = getWorkerDescription(worker.name);

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3 transition-colors',
        worker.running
          ? isCritical
            ? 'border border-[#76B900]/30 bg-[#76B900]/10'
            : 'bg-gray-800/50'
          : 'border border-red-500/30 bg-red-500/10'
      )}
      data-testid={`worker-row-${worker.name}`}
    >
      <div className="flex items-center gap-3">
        {/* Status Icon */}
        {worker.running ? (
          <CheckCircle
            className={clsx('h-5 w-5', isCritical ? 'text-[#76B900]' : 'text-green-500')}
            data-testid={`worker-icon-running-${worker.name}`}
          />
        ) : (
          <XCircle className="h-5 w-5 text-red-500" data-testid={`worker-icon-stopped-${worker.name}`} />
        )}

        {/* Worker Info */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <Text className="text-sm font-medium text-gray-300">{displayName}</Text>
            {isCritical && (
              <Badge color="amber" size="xs" data-testid={`critical-badge-${worker.name}`}>
                Critical
              </Badge>
            )}
          </div>
          <Text className="text-xs text-gray-500">{description}</Text>
          {worker.message && !worker.running && (
            <Text className="mt-1 text-xs text-red-400">{worker.message}</Text>
          )}
        </div>
      </div>

      {/* Status Badge */}
      <Badge color={worker.running ? 'green' : 'red'} size="sm" data-testid={`worker-status-badge-${worker.name}`}>
        {worker.running ? 'Running' : 'Stopped'}
      </Badge>
    </div>
  );
}

/**
 * WorkerStatusPanel - Displays the status of all background workers
 *
 * Shows:
 * - All 8 background workers with their current status
 * - Critical workers (detection_worker, analysis_worker) with special highlighting
 * - Running/stopped indicators with appropriate icons
 * - Error messages for stopped workers
 *
 * Fetches data from GET /api/system/health/ready endpoint.
 */
export default function WorkerStatusPanel({
  pollingInterval = 10000,
  onStatusChange,
}: WorkerStatusPanelProps) {
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchWorkerStatus = useCallback(async () => {
    try {
      const response = await fetchReadiness();
      const newWorkers = response.workers || [];
      setWorkers(newWorkers);
      setLastUpdated(new Date(response.timestamp));
      setError(null);
      onStatusChange?.(newWorkers);
    } catch (err) {
      console.error('Failed to fetch worker status:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch worker status');
    } finally {
      setLoading(false);
    }
  }, [onStatusChange]);

  // Initial fetch
  useEffect(() => {
    void fetchWorkerStatus();
  }, [fetchWorkerStatus]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchWorkerStatus();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchWorkerStatus]);

  // Calculate summary stats
  const runningCount = workers.filter((w) => w.running).length;
  const stoppedCount = workers.filter((w) => !w.running).length;
  const criticalRunning = workers.filter((w) => isCriticalWorker(w.name) && w.running).length;
  const criticalTotal = workers.filter((w) => isCriticalWorker(w.name)).length;

  // Sort workers: critical first, then alphabetical
  const sortedWorkers = [...workers].sort((a, b) => {
    const aCritical = isCriticalWorker(a.name);
    const bCritical = isCriticalWorker(b.name);
    if (aCritical && !bCritical) return -1;
    if (!aCritical && bCritical) return 1;
    return a.name.localeCompare(b.name);
  });

  // Loading state
  if (loading) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="worker-status-panel-loading">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          Background Workers
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="worker-status-panel-error">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          Background Workers
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load worker status</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="worker-status-panel">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          Background Workers
        </Title>

        {/* Summary Badge */}
        <div className="flex items-center gap-2">
          {stoppedCount > 0 && (
            <Badge color="red" size="sm" data-testid="stopped-count-badge">
              {stoppedCount} Stopped
            </Badge>
          )}
          <Badge
            color={criticalRunning === criticalTotal ? 'green' : 'red'}
            size="sm"
            data-testid="critical-summary-badge"
          >
            Critical: {criticalRunning}/{criticalTotal} Running
          </Badge>
        </div>
      </div>

      {/* Status Summary */}
      <div className="mb-4 flex items-center justify-center gap-6 rounded-lg bg-gray-800/30 p-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500"></div>
          <Text className="text-sm text-gray-300">
            <span className="font-bold text-white">{runningCount}</span> Running
          </Text>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-red-500"></div>
          <Text className="text-sm text-gray-300">
            <span className="font-bold text-white">{stoppedCount}</span> Stopped
          </Text>
        </div>
      </div>

      {/* Workers List */}
      <div className="space-y-2" data-testid="workers-list">
        {sortedWorkers.length > 0 ? (
          sortedWorkers.map((worker) => <WorkerStatusRow key={worker.name} worker={worker} />)
        ) : (
          <Text className="py-4 text-center text-gray-500">No worker status available</Text>
        )}
      </div>

      {/* Last Updated */}
      {lastUpdated && (
        <Text className="mt-4 text-xs text-gray-500" data-testid="last-updated">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Text>
      )}
    </Card>
  );
}
