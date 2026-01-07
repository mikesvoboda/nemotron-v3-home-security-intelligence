import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { CheckCircle, XCircle, Cpu, AlertTriangle, Star, ChevronDown, ChevronUp } from 'lucide-react';
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
  /** Whether the panel starts expanded (default: false for dense mode) */
  defaultExpanded?: boolean;
  /** Whether to show in compact mode (default: false) */
  compact?: boolean;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * List of essential workers that require special highlighting.
 * These workers are essential for the AI processing pipeline.
 */
const ESSENTIAL_WORKERS = ['detection_worker', 'analysis_worker'];

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
 * Checks if a worker is essential for the AI pipeline
 */
function isEssentialWorker(name: string): boolean {
  return ESSENTIAL_WORKERS.includes(name);
}

/**
 * WorkerStatusRow - Displays a single worker's status
 */
interface WorkerStatusRowProps {
  worker: WorkerStatus;
}

function WorkerStatusRow({ worker }: WorkerStatusRowProps) {
  const isEssential = isEssentialWorker(worker.name);
  const displayName = getWorkerDisplayName(worker.name);
  const description = getWorkerDescription(worker.name);

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3 transition-colors',
        worker.running
          ? isEssential
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
            className={clsx('h-5 w-5', isEssential ? 'text-[#76B900]' : 'text-green-500')}
            data-testid={`worker-icon-running-${worker.name}`}
          />
        ) : (
          <XCircle className="h-5 w-5 text-red-500" data-testid={`worker-icon-stopped-${worker.name}`} />
        )}

        {/* Worker Info */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <Text className="text-sm font-medium text-gray-300">{displayName}</Text>
            {isEssential && (
              <span title="Essential for AI pipeline">
                <Star
                  className="h-3.5 w-3.5 fill-[#76B900] text-[#76B900]"
                  data-testid={`essential-icon-${worker.name}`}
                  aria-label="Essential for AI pipeline"
                />
              </span>
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
 * - Essential workers (detection_worker, analysis_worker) with special highlighting
 * - Running/stopped indicators with appropriate icons
 * - Error messages for stopped workers
 * - Collapsible design with summary badge (e.g., "8/8 Running")
 *
 * Fetches data from GET /api/system/health/ready endpoint.
 */
export default function WorkerStatusPanel({
  pollingInterval = 10000,
  onStatusChange,
  defaultExpanded = false,
  compact = false,
  'data-testid': testId = 'worker-status-panel',
}: WorkerStatusPanelProps) {
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

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

  // Sort workers: essential first, then alphabetical
  const sortedWorkers = [...workers].sort((a, b) => {
    const aEssential = isEssentialWorker(a.name);
    const bEssential = isEssentialWorker(b.name);
    if (aEssential && !bEssential) return -1;
    if (!aEssential && bEssential) return 1;
    return a.name.localeCompare(b.name);
  });

  // Check for any stopped essential workers
  const essentialStopped = workers.filter(
    (w) => !w.running && isEssentialWorker(w.name)
  );
  const hasEssentialStopped = essentialStopped.length > 0;

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
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        hasEssentialStopped && 'border-red-500/50'
      )}
      data-testid={testId}
    >
      {/* Collapsible Header */}
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="worker-panel-toggle"
        aria-expanded={isExpanded}
        aria-controls="worker-list-content"
      >
        <Title className="flex items-center gap-2 text-white">
          <Cpu className="h-5 w-5 text-[#76B900]" />
          Background Workers
          {hasEssentialStopped && (
            <AlertTriangle
              className="h-4 w-4 text-red-500"
              data-testid="essential-worker-warning"
              aria-label="Essential worker stopped"
            />
          )}
        </Title>

        <div className="flex items-center gap-2">
          {/* Summary Badges */}
          {stoppedCount > 0 && (
            <Badge color="red" size="sm" data-testid="stopped-count-badge">
              {stoppedCount} Stopped
            </Badge>
          )}
          <Badge
            color={runningCount === workers.length ? 'green' : 'amber'}
            size="sm"
            data-testid="running-count-badge"
          >
            {runningCount}/{workers.length} Running
          </Badge>
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
        id="worker-list-content"
        className={clsx(
          'overflow-hidden transition-all duration-300 ease-in-out',
          isExpanded ? 'mt-4 max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
        )}
        data-testid="worker-list-content"
      >
        {/* Compact Status Summary */}
        {!compact && (
          <div className="mb-4 flex items-center justify-center gap-6 rounded-lg bg-gray-800/30 p-3">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" aria-hidden="true" />
              <div className="h-2 w-2 rounded-full bg-green-500" aria-hidden="true"></div>
              <Text className="text-sm text-gray-300">
                <span className="font-bold text-white">{runningCount}</span> Running
              </Text>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />
              <div className="h-2 w-2 rounded-full bg-red-500" aria-hidden="true"></div>
              <Text className="text-sm text-gray-300">
                <span className="font-bold text-white">{stoppedCount}</span> Stopped
              </Text>
            </div>
          </div>
        )}

        {/* Workers List */}
        <div className={clsx('space-y-2', compact && 'space-y-1')} data-testid="workers-list">
          {sortedWorkers.length > 0 ? (
            sortedWorkers.map((worker) => (
              <WorkerStatusRow key={worker.name} worker={worker} />
            ))
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
      </div>
    </Card>
  );
}
